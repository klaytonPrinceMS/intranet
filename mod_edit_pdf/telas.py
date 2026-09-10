"""Editor de PDF screen — manual upload/selection/split (Fase 5.5) + admin tab.

Tela do módulo Editor de PDF — envio manual/seleção/corte (Fase 5.5)
+ aba Administração exclusiva do administrador geral (Fase 5.6). Todos os
botões de ação usam o MESMO padrão (`ui_comum.botao`, variante `primario`
do tema do módulo) e o módulo inicia com as cores do seu próprio padrão
(`tema_modulo.PADROES_TEMA`), configuráveis no cupê Aparência da aba
Administração.

NiceGUI 3.x: eventos de upload usam FileUpload (.name/.size()/await .save())
e MultiUploadEventArguments (.files).
"""
import sys, os, time
from collections import deque
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from nicegui import ui

from mod_intranet.bd_conexao import get_config, set_config
from mod_intranet.bd_manipulador import audit_log
from mod_intranet.tema_modulo import (
    bloco_aparencia, campo_modulo, ler_tema, notificar)
from mod_intranet.ui_comum import botao
from mod_intranet import observabilidade

log = observabilidade.get_logger("edit_pdf")

from mod_edit_pdf.bd_manipulador import (
    pasta_usuario, nome_padronizado, registrar_arquivo, obter_meus_arquivos,
    op_reduzir, op_juntar, op_dividir, op_cortar, op_verificar,
    op_dividir_partes,
    zip_por_ids, deletar_arquivo, verificar_quota, contar_uploads_ativos,
    hash_sha256, uso_global_bytes, expirar_antigos,
    cfg_lote_arquivos, cfg_lote_mb, cfg_usuario_gb, cfg_expiracao_min,
)

JANELA_LOTE_S = 60  # janela temporal do controle de lote (não configurável)


def _fmt_bytes(n):
    """Formats a byte count as KB/MB/GB for display."""
    if n >= 1024**3:
        return f"{n/1024**3:.1f} GB"
    if n >= 1024**2:
        return f"{n/1024**2:.1f} MB"
    return f"{n/1024:.0f} KB"


def _fmt_resta(seg):
    """Formats remaining seconds as 'm:ss' (countdown label)."""
    seg = max(0, int(seg))
    return f"{seg // 60}:{seg % 60:02d}"


def _cor_resta(seg):
    """Vermelho no último minuto; amarelo até ~5 min; verde acima."""
    if seg <= 60:
        return "red-8"
    if seg <= 300:
        return "amber-8"
    return "green-8"


def mostrar_tela(usuario_logado: str, perfil: str):
    """Renders the PDF editor screen (editor + administration tab).

    Monta a tela completa: cabeçalho com cota do usuário (uso global só para
    admin geral), upload em lote com pré-checagem e recusas nominais, tabela
    de arquivos com seleção ordenada e contagem regressiva de expiração
    (timer 5 s), operações (reduzir/juntar/cortar/dividir/verificar/ZIP/
    excluir) e aba Administração (cotas, limites, textos da tela, aparência
    e manutenção) exclusiva do `administrador_geral`."""
    pasta = pasta_usuario(usuario_logado)
    lote = deque()  # (timestamp, bytes) do lote atual de upload
    sel_ids = set()
    ordem_ids = []  # ids NA ORDEM EM QUE O USUÁRIO MARCOU (define a ordem do merge)

    eh_admin_geral = perfil == "administrador_geral"

    # ---- Configurações dinâmicas (editadas na aba Administração) ----
    lote_max = cfg_lote_arquivos()
    lote_bytes_max = cfg_lote_mb() * 1024**2
    usuario_gb = cfg_usuario_gb()
    vida_pdf_s = cfg_expiracao_min() * 60

    # ---- Tema padronizado (cores e tamanho dos botões) ----
    tema = ler_tema("editar_pdf", cor_botao="#000000", cor_texto_botao="#FFFFFF",
                    cor_titulo="#212121")
    ui.colors(primary=tema["cor_botao"])

    def _app_tema():
        """Aplica cor de fundo do editor (se configurada) e cor do título."""
        try:
            if tema["cor_fundo"]:
                ui.query(".q-page").style(
                    f"background-color:{tema['cor_fundo']}")
        except Exception as e:
            log.warning(f"_app_tema: falha ao aplicar cor de fundo | {e}")
        try:
            for it in (lbl_header_titulo, lbl_up_titulo, lbl_header_sub,):
                if it is not None:
                    it.style(f"color:{tema['cor_titulo']}")
        except Exception as e:
            log.warning(f"_app_tema: falha ao aplicar cor do título | {e}")

    txt_upload_titulo = get_config("editar_pdf_texto_upload_titulo",
                                   "Envie um ou mais PDFs") or "Envie um ou mais PDFs"
    txt_upload_hint = get_config("editar_pdf_texto_upload_hint",
                                 "") or ""
    txt_upload_label = get_config("editar_pdf_texto_upload_label",
                                  "Clique ou arraste PDFs aqui") or "Clique ou arraste PDFs aqui"
    txt_header_sub = get_config("editar_pdf_texto_header_sub",
                                "Reduza, junte, corte, divida e verifique seus documentos.") \
        or "Reduza, junte, corte, divida e verifique seus documentos."

    # ================= HANDLERS (todos antes da UI que os usa) =================

    async def _receber_lote(e):
        """Recebe o LOTE completo de arquivos e decide quais entram no servidor.

        Recusados são listados NOMINALMENTE com motivo — nunca falha silencioso.
        """
        try:
            agora = time.time()
            while lote and agora - lote[0][0] > JANELA_LOTE_S:
                lote.popleft()

            enviados, recusados = [], []
            ativos_upload = contar_uploads_ativos(usuario_logado)
            pdfs = [f for f in e.files if (f.name or "").lower().endswith(".pdf")]
            nao_pdf = [f.name for f in e.files if f not in pdfs]

            # ---- Pré-checagem do LOTE inteiro (não só incremental) ----
            # Métrica usada como N teto de upload de UMA vez. Impede que uma
            # seleção grande (ex.: 100 arquivos/350 MB) escape do limite de MB
            # quando o navegador divide o envio em várias janelas de 60 s.
            total_lote_bytes = sum(f.size() for f in pdfs)
            if ativos_upload + len(pdfs) > lote_max:
                for f in pdfs:
                    recusados.append((f.name,
                                      f"limite de {lote_max} arquivos 'upload' no seu espaço "
                                      f"— já tem {ativos_upload}; aguarde expiração ou exclua"))
            elif total_lote_bytes > lote_bytes_max:
                for f in pdfs:
                    recusados.append((f.name, f"este envio de {_fmt_bytes(total_lote_bytes)} "
                                              f"excede o máximo de {_fmt_bytes(lote_bytes_max)} por lote"))
            else:
                for f in pdfs:
                    bytes_janela = sum(b for _, b in lote)
                    if len(lote) >= lote_max:
                        recusados.append((f.name, f"lote de {lote_max} arquivos atingido"))
                        continue
                    if bytes_janela + f.size() > lote_bytes_max:
                        recusados.append((f.name, f"limite de {_fmt_bytes(lote_bytes_max)} por lote"))
                        continue
                    ok_q, msg_q = verificar_quota(usuario_logado, f.size())
                    if not ok_q:
                        recusados.append((f.name, msg_q))
                        continue

                    nome = f.name or ""
                    destino = os.path.join(pasta, nome_padronizado(usuario_logado, "upload", nome))
                    await f.save(destino)
                    rid = registrar_arquivo(usuario_logado, destino, "upload")
                    if rid:
                        lote.append((agora, f.size()))
                        enviados.append(nome)
                        ativos_upload += 1
                        try:
                            audit_log(usuario_logado, "edit-pdf", "upload_hash",
                                      f"{nome} sha256={hash_sha256(destino)}")
                        except Exception:
                            pass
                    else:
                        try:
                            os.remove(destino)
                        except OSError:
                            pass
                        recusados.append((f.name, "falha ao registrar"))

            for nome in nao_pdf:
                recusados.append((nome, "formato não-PDF"))

            if enviados:
                resumo = ", ".join(enviados[:5]) + ("…" if len(enviados) > 5 else "")
                info_ok.set_text(f"Enviado(s): {len(enviados)} — {resumo}").classes(
                    "text-caption text-green-8")
            else:
                info_ok.set_text("Nenhum arquivo novo enviado.").classes("text-caption text-grey-6")

            if recusados:
                detalhe = " | ".join(f"'{n}' ({m})" for n, m in recusados)
                info_rec.set_text(f"NÃO ENVIADOS ({len(recusados)}) → {detalhe}").classes(
                    "text-caption text-red-8")
            else:
                info_rec.set_text("")

            up.reset()
            if enviados and not recusados:
                notificar(f"{len(enviados)} arquivo(s) enviado(s) ao servidor", type="positive")
            elif enviados:
                notificar(f"{len(enviados)} enviado(s); {len(recusados)} NÃO enviado(s) — veja a lista",
                          type="warning", multi_line=True)
            else:
                notificar(f"Nenhum arquivo foi enviado ({len(recusados)} recusado(s)) — veja a lista",
                          type="negative", multi_line=True)
            atualizar_tabela()
        except Exception as ex:
            log.exception("erro interno no upload de lote")
            notificar(f"Erro interno no upload: {ex}", type="negative", multi_line=True)

    def _rows_do_evento(e):
        """NiceGUI 3.x: seleção chega como .selection, dict {'added','rows','keys'}
        ou lista — cobrir todos os formatos."""
        rows = getattr(e, "selection", None)
        if rows is None:
            a = getattr(e, "args", None)
            if isinstance(a, dict):
                rows = a.get("rows") or []
            elif isinstance(a, list):
                rows = a
            else:
                rows = []
        return rows or []

    _ultimo_refresh = [0.0]
    _reaplicando = [False]  # True durante re-marcação automática: ignora eco

    def _ao_selecionar(e):
        if _reaplicando[0]:
            return  # eco da re-aplicação pós-refresh (não foi ação do usuário)
        rows = _rows_do_evento(e)
        if not rows and time.time() - _ultimo_refresh[0] < 1.0:
            return  # ruído do re-render automático (não foi ação do usuário)
        novos = [r["id"] for r in rows if isinstance(r, dict) and "id" in r]
        if getattr(e, "selection", None) is not None:
            # Evento pleno do NiceGUI 3.x: selection chega NA ORDEM DE CLIQUE
            # do cliente (extend a cada marcação) — é a MESMA fonte dos
            # badges "#". Confiar nela integralmente evita divergência
            # entre o número exibido e a ordem usada pelo Juntar.
            ordem_ids[:] = []
            vistos = set()
            for rid in novos:
                if rid not in vistos:
                    vistos.add(rid)
                    ordem_ids.append(rid)
        else:
            # Fallback legado (dict {'added','rows','keys'} / lista parcial):
            # mantém quem já está na fila e anexa os novos ao fim.
            for rid in novos:
                if rid not in ordem_ids:
                    ordem_ids.append(rid)
            for rid in [x for x in ordem_ids if x not in novos]:
                ordem_ids.remove(rid)
        sel_ids.clear()
        sel_ids.update(ordem_ids)
        lbl_res.set_text(f"{len(sel_ids)} selecionado(s)")
        _renumerar()

    def _renumerar():
        """Mostra ao lado do checkbox o número da marcação (1º, 2º, …)."""
        pos = {rid: i + 1 for i, rid in enumerate(ordem_ids)}
        for r in tabela.rows:
            r["sel_n"] = str(pos[r["id"]]) if r["id"] in pos else ""
        tabela.update()

    def _reaplicar_selecao():
        """Re-marca os checkboxes após o cliente receber rows novas
        (serialização troca referências e o Quasar solta a marcação).
        Repõe NA ORDEM DE MARCAÇÃO (ordem_ids) — nunca na ordem da tabela —
        e silencia o eco dos eventos disparados por esta re-marcação."""
        if not sel_ids or not tabela.rows:
            return
        _reaplicando[0] = True
        try:
            por_id = {r["id"]: r for r in tabela.rows}
            tabela.selected = [por_id[rid] for rid in ordem_ids if rid in por_id]
            tabela.update()
        finally:
            ui.timer(1.0, lambda: _reaplicando.__setitem__(0, False), once=True)

    def atualizar_tabela():
        agora = time.time()
        pos = {rid: i + 1 for i, rid in enumerate(ordem_ids)}
        dados, ordem = {}, []
        for r in obter_meus_arquivos(usuario_logado):
            rid, nome, tam, op, dt = r
            try:
                mtime = os.path.getmtime(os.path.join(pasta, nome))
            except OSError:
                mtime = agora
            resta = vida_pdf_s - (agora - mtime)
            dados[rid] = {"id": rid, "nome": nome, "tam": _fmt_bytes(tam),
                          "op": op,
                          "resta": _fmt_resta(resta),
                          "cor": _cor_resta(resta),
                          "sel_n": str(pos[rid]) if rid in pos else "",
                          "dt": (dt or "")[:16]}
            ordem.append(rid)
        # ids marcados que sumiram da lista (expirados) saem da fila
        for rid in [x for x in ordem_ids if x not in set(ordem)]:
            ordem_ids.remove(rid)
        atuais = {r["id"]: r for r in tabela.rows}
        if set(ordem) != set(atuais):
            tabela.rows = [dados[i] for i in ordem]  # conjunto mudou
        else:
            for i in ordem:
                atuais[i].update(dados[i])  # mesmos ids: muta in-place, preserva refs
        tabela.update()
        _ultimo_refresh[0] = time.time()
        if sel_ids:
            ui.timer(0.2, _reaplicar_selecao, once=True)

    def _alvos():
        """Caminhos dos arquivos SELECIONADOS NA ORDEM DE MARCAÇÃO, ou None com aviso."""
        if not ordem_ids:
            notificar("Marque ao menos um arquivo na lista abaixo", type="warning")
            return None
        por_id = {r["id"]: r for r in tabela.rows}
        return [os.path.join(pasta, por_id[rid]["nome"])
                for rid in ordem_ids if rid in por_id]

    def _auditar_hash(operacao, origem, destino):
        """Auditoria LGPD: hash SHA-256 completo de origem(s) → destino
        (campo dedicado hash_arquivo recebe o hash do resultado)."""
        try:
            origens = origem if isinstance(origem, list) else [origem]
            hos = ";".join(
                hash_sha256(o) if o and os.path.exists(o) else "-" for o in origens)
            hd = (hash_sha256(destino)
                  if destino and os.path.exists(destino) else "-")
            audit_log(usuario_logado, "edit-pdf", operacao,
                      f"sha256 origem=[{hos}]",
                      hash_arquivo=hd)
        except Exception:
            pass

    def _registrar_saida(caminho_out):
        rid = registrar_arquivo(usuario_logado, caminho_out, "saida")
        if rid:
            notificar(f"Gerado: {os.path.basename(caminho_out)}", type="positive")
            atualizar_tabela()

    def _op_reduzir():
        alvos = _alvos()
        if not alvos:
            return
        feitos = falhas = 0
        for caminho in alvos:
            out = os.path.join(pasta, nome_padronizado(usuario_logado, "reduzido",
                                                       os.path.basename(caminho)))
            ok, msg = op_reduzir(caminho, out, qualidade=qual.value,
                                 dpi=dpi_red.value, modo=modo_red.value,
                                 biblioteca=bib_red.value)
            if ok and os.path.exists(out):
                _registrar_saida(out)
                _auditar_hash("reduzir", caminho, out)
                feitos += 1
            else:
                falhas += 1
                audit_log(usuario_logado, "edit-pdf", "erro_reducao",
                          f"{os.path.basename(caminho)}: {msg}",
                          hash_arquivo=(hash_sha256(caminho)
                                        if os.path.exists(caminho) else None))
                notificar(f"Erro ao reduzir {os.path.basename(caminho)}: {msg}", type="negative")
        notificar(f"{feitos} reduzido(s), {falhas} falha(s)",
                  type="positive" if feitos else "negative")

    def _op_juntar():
        alvos = _alvos()
        if not alvos:
            return
        if len(alvos) < 2:
            notificar("Selecione ao menos 2 PDFs para juntar", type="warning")
            return
        out = os.path.join(pasta, nome_padronizado(usuario_logado, "junto", "documento_final.pdf"))
        ok, msg = op_juntar(alvos, out)
        if ok:
            _registrar_saida(out)
            _auditar_hash("juntar",
                          [a for a in alvos if str(a).lower().endswith(".pdf")], out)
            ordem_nomes = " → ".join(os.path.basename(a) for a in alvos)
            notificar(f"Junção na ordem dos # : {ordem_nomes}",
                      type="info", multi_line=True)
            notificar(f"Juntado: {msg}", type="warning" if "IGNORADOS" in msg else "positive",
                      multi_line=True)
        else:
            notificar(f"Nada foi juntado: {msg}", type="negative", multi_line=True)

    def _op_cortar_sel(biblioteca="pymupdf"):
        alvos = _alvos()
        if not alvos:
            return
        modo = modo_corte.value
        filtro = modo if modo in ("pares", "impares") else paginas_corte.value
        feitos = falhas = 0
        for caminho in alvos:
            base = nome_padronizado(usuario_logado, "cortado",
                                    os.path.splitext(os.path.basename(caminho))[0])
            ok, res = op_cortar(caminho, filtro, pasta, base,
                                biblioteca=biblioteca)
            if ok:
                _registrar_saida(res)
                _auditar_hash("cortar", caminho, res)
                feitos += 1
            else:
                falhas += 1
                notificar(f"Corte sem efeito em '{os.path.basename(caminho)}': {res} "
                          f"(filtro '{filtro}', bib '{biblioteca}')",
                          type="warning", multi_line=True)
        notificar(f"{feitos} corte(s) gerado(s)", type="positive" if feitos else "info")

    def _op_dividir():
        alvos = _alvos()
        if not alvos:
            return
        modo = modo_div.value
        bib = bib_pg.value
        parametro = {"pagina": paginas_in.value,
                     "cortes": corte_in.value,
                     "intervalos": intervalos_in.value}.get(modo, "")
        feitos = 0
        for caminho in alvos:
            base = nome_padronizado(usuario_logado, "dividido",
                                    os.path.splitext(os.path.basename(caminho))[0])
            try:
                ok, dados, aviso = op_dividir_partes(
                    caminho, modo, parametro, pasta, base, biblioteca=bib)
            except Exception as ex:
                log.exception(f"erro ao dividir {os.path.basename(caminho)}")
                notificar(f"Erro ao dividir {os.path.basename(caminho)}: {ex}",
                          type="negative")
                continue
            if not ok:
                notificar(f"'{os.path.basename(caminho)}': {dados}",
                          type="warning", multi_line=True)
                continue
            for caminho_p, _sufixo in dados:
                _registrar_saida(caminho_p)
                feitos += 1
            audit_log(usuario_logado, "edit-pdf", "dividir",
                      f"modo={modo} filtro='{parametro}' bib={bib} "
                      f"arquivos={len(dados)} sha256_origem={hash_sha256(caminho)}")
            if aviso:
                notificar(f"{os.path.basename(caminho)}: {aviso}",
                          type="warning", multi_line=True)
        notificar(f"{feitos} arquivo(s) gerado(s)",
                  type="positive" if feitos else "info")

    def _op_verificar():
        alvos = _alvos()
        if not alvos:
            return
        for caminho in alvos:
            ok, msg = op_verificar(caminho)
            notificar(f"{os.path.basename(caminho)}: {msg}", type="positive" if ok else "negative")

    def baixar_zip():
        if not sel_ids:
            notificar("Marque ao menos um arquivo para baixar", type="warning")
            return
        z = zip_por_ids(usuario_logado, list(ordem_ids))
        if z:
            try:
                audit_log(usuario_logado, "edit-pdf", "zip",
                          f"arquivos={len(sel_ids)} sha256={hash_sha256(z)}")
            except Exception:
                pass
            ui.download(z, filename=os.path.basename(z))
            ui.timer(10.0, lambda p=z: os.remove(p) if os.path.exists(p) else None,
                     once=True)
            atualizar_tabela()
        else:
            notificar("Nenhum arquivo válido na seleção", type="info")

    def excluir_selecionados():
        if not sel_ids:
            notificar("Marque ao menos um arquivo para excluir", type="warning")
            return
        n = len(ordem_ids)
        for rid in list(ordem_ids):
            deletar_arquivo(usuario_logado, rid)
        sel_ids.clear()
        ordem_ids.clear()
        lbl_res.set_text("")
        atualizar_tabela()
        notificar(f"{n} arquivo(s) excluído(s)", type="info")

    def baixar_originais():
        """Baixa CADA arquivo marcado individualmente, sem compactar (ordem da numeração)."""
        if not sel_ids:
            notificar("Marque ao menos um arquivo para baixar", type="warning")
            return
        por_id = {r["id"]: r for r in tabela.rows}
        validos = 0
        for rid in list(ordem_ids):
            r = por_id.get(rid)
            if not r:
                continue
            caminho = os.path.join(pasta, r["nome"])
            if os.path.exists(caminho):
                validos += 1
                ui.download(caminho, filename=r["nome"])
        if not validos:
            notificar("Nenhum arquivo válido na seleção", type="info")
        else:
            notificar(f"Iniciando {validos} download(s) — permita múltiplos "
                      "downloads se o navegador perguntar.", type="info")

    def salvar_configs():
        nonlocal lote_max, lote_bytes_max, usuario_gb, vida_pdf_s
        nonlocal txt_upload_titulo, txt_upload_hint, txt_upload_label, txt_header_sub
        try:
            gb_g = max(1, int(inp_cota_global.value or 10))
            lot_a = max(1, int(inp_lote_arq.value or 10))
            lot_mb = max(1, int(inp_lote_mb.value or 1024))
            usr_g = max(1, int(inp_usuario_gb.value or 1))
            exp_m = max(1, int(inp_expira_min.value or 10))
            set_config("cotadisco_global_gb", gb_g)
            set_config("editar_pdf_lote_arquivos", lot_a)
            set_config("editar_pdf_lote_mb", lot_mb)
            set_config("editar_pdf_usuario_gb", usr_g)
            set_config("editar_pdf_expiracao_min", exp_m)
            lote_max = lot_a
            lote_bytes_max = lot_mb * 1024**2
            usuario_gb = usr_g
            vida_pdf_s = exp_m * 60
            txt_upload_titulo = (inp_txt_titulo.value or "").strip() or "Envie um ou mais PDFs"
            txt_upload_hint = (inp_txt_hint.value or "").strip()
            txt_upload_label = (inp_txt_label.value or "").strip() or "Clique ou arraste PDFs aqui"
            txt_header_sub = (inp_txt_header.value or "").strip() \
                or "Reduza, junte, corte, divida e verifique seus documentos."
            set_config("editar_pdf_texto_upload_titulo", txt_upload_titulo)
            set_config("editar_pdf_texto_upload_hint", txt_upload_hint)
            set_config("editar_pdf_texto_upload_label", txt_upload_label)
            set_config("editar_pdf_texto_header_sub", txt_header_sub)
            _app_tema()
        except Exception as ex:
            log.exception("erro ao salvar configurações do editor PDF")
            notificar(f"Erro ao salvar configurações: {ex}", type="negative")
            return
        try:
            lbl_up_titulo.set_text(f"1. {txt_upload_titulo}")
            lbl_up_hint.set_text(_montar_hint())
            lbl_header_sub.set_text(txt_header_sub)
        except Exception:
            pass
        try:
            audit_log(usuario_logado, "edit-pdf", "configuracao",
                      f"cota_global={gb_g}GB lote={lot_a}arq/{lot_mb}MB "
                      f"cota_usuario={usr_g}GB expiracao={exp_m}min")
        except Exception:
            pass
        notificar("Configurações salvas — valem imediatamente, sem restart.",
                  type="positive")

    def expirar_agora():
        n = expirar_antigos(minutos=cfg_expiracao_min())
        notificar(f"{n} arquivo(s) removido(s) pela expiração manual", type="info")
        atualizar_tabela()

    PADROES_CFG = {
        "cotadisco_global_gb": "10",
        "editar_pdf_lote_arquivos": "10",
        "editar_pdf_lote_mb": "1024",
        "editar_pdf_usuario_gb": "1",
        "editar_pdf_expiracao_min": "10",
        "editar_pdf_texto_upload_titulo": "Envie um ou mais PDFs",
        "editar_pdf_texto_upload_hint": "",
        "editar_pdf_texto_upload_label": "Clique ou arraste PDFs aqui",
        "editar_pdf_texto_header_sub": "Reduza, junte, corte, divida e verifique seus documentos.",
        "editpdf_cor_botao": "#000000",
        "editpdf_cor_texto_botao": "#FFFFFF",
        "editpdf_cor_fundo": "",
        "editpdf_cor_titulo": "#212121",
        "editpdf_btn_tamanho": "medium",
    }

    def resetar_configs():
        nonlocal lote_max, lote_bytes_max, usuario_gb, vida_pdf_s
        nonlocal txt_upload_titulo, txt_upload_hint, txt_upload_label, txt_header_sub
        try:
            for chave, valor in PADROES_CFG.items():
                set_config(chave, valor)
            lote_max = 10
            lote_bytes_max = 1024 * 1024**2
            usuario_gb = 1
            vida_pdf_s = 10 * 60
            txt_upload_titulo = "Envie um ou mais PDFs"
            txt_upload_hint = ""
            txt_upload_label = "Clique ou arraste PDFs aqui"
            txt_header_sub = "Reduza, junte, corte, divida e verifique seus documentos."
            inp_cota_global.value = 10
            inp_lote_arq.value = 10
            inp_lote_mb.value = 1024
            inp_usuario_gb.value = 1
            inp_expira_min.value = 10
            inp_txt_titulo.value = txt_upload_titulo
            inp_txt_hint.value = txt_upload_hint
            inp_txt_label.value = txt_upload_label
            inp_txt_header.value = txt_header_sub
            lbl_up_titulo.set_text(f"1. {txt_upload_titulo}")
            lbl_up_hint.set_text(_montar_hint())
            lbl_header_sub.set_text(txt_header_sub)
            _app_tema()
            audit_log(usuario_logado, "edit-pdf", "configuracao",
                      "reset para padroes de fabrica")
            notificar("Configurações restauradas para o padrão de fábrica.",
                      type="positive")
        except Exception as ex:
            log.exception("erro ao resetar configurações do editor PDF")
            notificar(f"Erro ao resetar configurações: {ex}", type="negative")

    # ================= UI =================

    # ---- Cabeçalho ----
    arq = obter_meus_arquivos(usuario_logado)
    usados = sum(a[2] for a in arq)
    gb_global_atual = int(get_config("cotadisco_global_gb", "10") or 10)
    with ui.card().classes("w-full border-l-8").style(
            f'border-left-color:{tema["cor_botao"]}'):
        with ui.row().classes("w-full items-center justify-between flex-wrap gap-3"):
            with ui.column().classes("gap-0"):
                lbl_header_titulo = ui.label("Editor de PDF").classes("text-h5 font-bold")
                lbl_header_sub = ui.label(txt_header_sub).classes("text-caption text-grey-6")
                if eh_admin_geral:
                    ui.label(f"Uso global do servidor: {_fmt_bytes(uso_global_bytes())} "
                             f"/ {gb_global_atual} GB").classes("text-caption text-primary")
            with ui.row().classes("items-center gap-2"):
                ui.icon("data_usage").classes("text-primary")
                ui.linear_progress(min(usados / (usuario_gb * 1024**3), 1.0),
                                   show_value=False).classes("w-40")
                ui.label(f"{_fmt_bytes(usados)} / {usuario_gb} GB").classes(
                    "text-caption text-grey-7")

    # ---- Menu: Editor | Administração (exclusiva admin geral) ----
    tabs_el = ui.tabs(value="editor")
    with tabs_el:
        ui.tab("editor", label="Editor", icon="picture_as_pdf")

    with ui.tab_panels(tabs_el, value="editor").classes("w-full"):
        # ---------- PAINEL EDITOR ----------
        with ui.tab_panel("editor"):
            with ui.card().classes("w-full"):
                with ui.card_section().classes("gap-3 w-full"):
                    # --- Upload ---
                    lbl_up_titulo = ui.label(f"1. {txt_upload_titulo}") \
                        .classes("text-h6 font-bold text-grey-9")

                    def _montar_hint():
                        base = txt_upload_hint
                        if not base:
                            base = (f"Máximo por vez: {lote_max} arquivos ou "
                                    f"{_fmt_bytes(lote_bytes_max)}. Excedentes NÃO são enviados. "
                                    "Marque os checkboxes para escolher a operação. "
                                    "Clique numa linha para baixar/excluir.")
                        return base
                    lbl_up_hint = ui.label(_montar_hint()).classes("text-caption text-grey-6")
                    info_ok = ui.label("").classes("text-caption text-green-8")
                    info_rec = ui.label("").classes("text-caption text-red-8")
                    up = ui.upload(
                        label=txt_upload_label,
                        multiple=True,
                        auto_upload=True,
                        on_multi_upload=_receber_lote,
                    ).props("accept=.pdf").classes("w-full")

                    # --- Arquivos no servidor ---
                    with ui.row().classes("w-full items-center justify-end flex-wrap gap-2"):
                        lbl_res = ui.label("").classes("text-caption text-primary")
                        botao("Atualizar", icone="refresh", on_click=atualizar_tabela,
                              variante="primario", chave_modulo="editar_pdf",
                              tooltip="Atualizar lista")
                    colunas = [
                        {"name": "sel_n", "label": "#", "field": "sel_n"},
                        {"name": "nome", "label": "Arquivo", "field": "nome", "align": "left"},
                        {"name": "tam", "label": "Tamanho", "field": "tam"},
                        {"name": "op", "label": "Origem", "field": "op"},
                        {"name": "resta", "label": "Expira em", "field": "resta"},
                        {"name": "id", "label": "", "field": "id"},
                    ]
                    tabela = ui.table(columns=colunas, rows=[], row_key="id",
                                      selection="multiple", on_select=_ao_selecionar,
                                      ).props("flat bordered dense").classes("w-full")
                    tabela.add_slot("body-cell-resta", """
                        <q-td :props="props">
                            <q-badge :color="props.row.cor" :label="props.row.resta">
                                <q-tooltip>Enviado em {{ props.row.dt }} —
                                expira após o tempo configurado pelo administrador</q-tooltip>
                            </q-badge>
                        </q-td>
                    """)
                    tabela.add_slot("body-cell-sel_n", """
                        <q-td :props="props" style="width:48px; text-align:center;">
                            <q-badge v-if="props.value" color="primary" :label="props.value">
                                <q-tooltip>Ordem em que você marcou —
                                Juntar/Reduzir/Cortar seguem esta sequência</q-tooltip>
                            </q-badge>
                        </q-td>
                    """)

                    # Menu de contexto da linha (NiceGUI 3.x: ui.menu sem move_to_element)
                    linha_atual = [None]

                    def _baixar_linha(linha):
                        if not linha:
                            return
                        ui.download(os.path.join(pasta, linha["nome"]),
                                    filename=linha["nome"])

                    def _excluir_linha(linha):
                        if not linha:
                            return
                        deletar_arquivo(usuario_logado, linha["id"])
                        notificar("Arquivo excluído", type="info")
                        atualizar_tabela()

                    def on_row(e):
                        try:
                            linha_atual[0] = e.args[1]
                        except Exception:
                            log.debug("on_row: evento sem args esperados")
                        menu_linha.open()

                    with tabela:
                        with ui.context_menu() as menu_linha:
                            ui.item("Baixar", on_click=lambda: _baixar_linha(linha_atual[0]))
                            ui.item("Excluir", on_click=lambda: _excluir_linha(linha_atual[0]))
                    tabela.on("row-click", on_row)

                    ui.separator()

                    # --- Botões de ação centralizados (todos idênticos) ---
                    with ui.row().classes("w-full flex-wrap items-center justify-center gap-2"):
                        botao("Verificar integridade", icone="verified",
                              on_click=_op_verificar, variante="primario",
                              chave_modulo="editar_pdf")
                        botao("Juntar selecionados", icone="merge",
                              on_click=_op_juntar, variante="primario",
                              chave_modulo="editar_pdf",
                              tooltip="Segue a ordem de marcação dos checkboxes")
                        ui.separator().props("vertical").classes("self-stretch")
                        botao("Excluir selecionados", icone="delete",
                              on_click=excluir_selecionados, variante="primario",
                              chave_modulo="editar_pdf") \
                            .props('data-testid=editpdf-excluir')
                        botao("Baixar selecionados (ZIP)", icone="download",
                              on_click=baixar_zip, variante="primario",
                              chave_modulo="editar_pdf")
                        botao("Baixar selecionados (PDFs)",
                              icone="file_download",
                              on_click=baixar_originais, variante="primario",
                              chave_modulo="editar_pdf",
                              tooltip="Baixa cada PDF marcado individualmente, sem ZIP")
                        botao("Enviar agora", icone="upload",
                              on_click=lambda: up.run_method("upload"),
                              variante="primario", chave_modulo="editar_pdf",
                              tooltip="Reenvia arquivos que ficaram pendentes") \
                            .props('data-testid=editpdf-upload')

            # Operações
            with ui.grid(columns=2).classes("w-full gap-4 max-lg:grid-cols-2 max-sm:grid-cols-1"):
                with ui.card():
                    with ui.card_section().classes("gap-2 w-full"):
                        ui.label("2. Reduzir tamanho").classes("font-bold")
                        modo_red = ui.toggle({"leve": "Leve", "agressivo": "Agressivo"},
                                             value="leve").props("dense")
                        qual = ui.slider(min=10, max=100, value=50, step=10).props("label")
                        with ui.row().classes("items-center w-full"):
                            ui.label("Qualidade:").classes("text-caption")
                            lbl_q = ui.badge(f"{qual.value}%")
                            qual.on("update:model-value",
                                    lambda v: lbl_q.set_text(f"{v.args}%"))
                        dpi_red = ui.slider(min=50, max=400, value=150, step=10) \
                            .props("label").tooltip("DPI do raster no modo Agressivo (50–400)")
                        with ui.row().classes("items-center w-full"):
                            ui.label("DPI (agressivo):").classes("text-caption")
                            lbl_dpi = ui.badge(f"{int(dpi_red.value)}")
                            dpi_red.on("update:model-value",
                                       lambda v: lbl_dpi.set_text(str(int(v.args))))
                        bib_red = ui.select(
                            {"auto": "Automático", "pymupdf": "pymupdf",
                             "pikepdf": "pikepdf", "pypdf": "pypdf"},
                            value="auto", label="Biblioteca (modo Leve)",
                        ).props("outlined dense").classes("w-full") \
                            .tooltip("Automático tenta pymupdf → pikepdf → pypdf. "
                                     "No modo Agressivo o raster é sempre pymupdf.")
                        botao("Reduzir selecionados", icone="compress",
                              on_click=_op_reduzir, variante="primario",
                              chave_modulo="editar_pdf")

                with ui.card():
                    with ui.card_section().classes("gap-2 w-full"):
                        ui.label("3. Páginas — cortar / dividir").classes("font-bold")
                        bib_pg = ui.select(
                            {"auto": "Automático", "pymupdf": "pymupdf",
                             "pikepdf": "pikepdf", "pypdf": "pypdf"},
                            value="auto", label="Biblioteca",
                        ).props("outlined dense").classes("w-full") \
                            .tooltip("Usada no Cortar e no Dividir. "
                                     "Automático tenta pymupdf → pikepdf → pypdf.")

                        ui.label("CORTAR → um único PDF") \
                            .classes("text-caption font-bold text-grey-7")
                        modo_corte = ui.select(
                            {"impares": "Ímpares", "pares": "Pares",
                             "lista": "Personalizado"},
                            value="impares", label="Filtro",
                        ).props("outlined dense").classes("w-full")
                        paginas_corte = ui.input("Lista (ex.: 2-5,8)", value="1-3") \
                            .props("outlined dense").classes("w-full")
                        botao("Cortar selecionados", icone="content_cut",
                              on_click=lambda: _op_cortar_sel(bib_pg.value),
                              variante="primario", chave_modulo="editar_pdf")

                        ui.separator()

                        ui.label("DIVIDIR → vários PDFs") \
                            .classes("text-caption font-bold text-grey-7")
                        modo_div = ui.select(
                            {"pagina": "Página a página",
                             "parimpar": "Pares × Ímpares",
                             "cortes": "Cortes múltiplos",
                             "intervalos": "Intervalos"},
                            value="pagina", label="Modo de divisão",
                        ).props("outlined dense").classes("w-full")
                        paginas_in = ui.input("Páginas (ex.: 1,3-5 ou 'todas')",
                                              value="todas") \
                            .props("outlined dense").classes("w-full")
                        corte_in = ui.input("Cortar após a página (ex.: 5 ou 5,12)",
                                            value="5") \
                            .props("outlined dense").classes("w-full")
                        intervalos_in = ui.input("Intervalos (ex.: 1-4,5-9)",
                                                 value="1-4,5-9") \
                            .props("outlined dense").classes("w-full")
                        paginas_in.bind_visibility_from(
                            modo_div, "value", backward=lambda v: v == "pagina")
                        corte_in.bind_visibility_from(
                            modo_div, "value", backward=lambda v: v == "cortes")
                        intervalos_in.bind_visibility_from(
                            modo_div, "value", backward=lambda v: v == "intervalos")
                        botao("Dividir selecionados", icone="call_split",
                              on_click=_op_dividir, variante="primario",
                              chave_modulo="editar_pdf")

    _app_tema()
    atualizar_tabela()
    ui.timer(5.0, atualizar_tabela)  # contagem de vida ao vivo + expiração
