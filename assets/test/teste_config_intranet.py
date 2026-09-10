"""Teste do Config do módulo Intranet: Aplicar por card, aparência, avisos e fundo.

Script standalone (NÃO pytest). Valida o que foi codificado nas fases de
padronização do /configuracoes:
  - SEM botão geral APLICAR — cada card tem o rodapé padrão de 2 botões
    ("Restaurar padrão" + "Aplicar") tratando exclusivamente o card, com
    recarregamento após 1 segundo;
  - cards recolhíveis (`card_admin`) — um card por tema;
  - card "Configurações de cores" com prévia única ao vivo;
  - cards Ícones / Textos / Gerais;
  - helper anti-zeramento `_v()` e restore dos Textos com chaves reais;
  - `cor_fundo` pintando body + .q-page (login e layout);
  - avisos via `notificar()` com tempo configurável (`notificacao_timeout`);
  - alerta único de restart ao trocar cor.

Execute: .venv/bin/python test/teste_config_intranet.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_OK = 0
_TOTAL = 0


def check(cond, msg):
    global _OK, _TOTAL
    _TOTAL += 1
    if cond:
        _OK += 1
        print(f"  OK [{_OK}] {msg}")
    else:
        print(f"  FALHOU [{_TOTAL - _OK}] {msg}")


def ler(rel):
    with open(os.path.join(RAIZ, rel), encoding="utf-8") as f:
        return f.read()


print("INICIANDO TESTES — Config Intranet (Aplicar por card, aparência, avisos, fundo)")

TELA = ler("mod_intranet/tela_configuracoes.py")
MAIN = ler("main.py")
LAYOUT = ler("mod_intranet/telas.py")
TEMA = ler("mod_intranet/tema_modulo.py")

# ---------- APLICAR por card (sem APLICAR geral) ----------
check('_botao_padrao("APLICAR"' not in TELA and "salvar_tudo" not in TELA,
      "sem botão APLICAR geral na barra do Config")
check("SALVAR TUDO" not in TELA, "nenhum resquício de SALVAR TUDO")
check("ui.timer(1.0, lambda: ui.navigate.reload(), once=True)" in TELA,
      "Aplicar de cada card recarrega após 1 segundo")
check("rodape_salvar_restaurar(" in TELA and "aplicar_cores" in TELA
      and "aplicar_gerais" in TELA and "aplicar_obs" in TELA,
      "padrão de 2 botões por card (Restaurar padrão + Aplicar)")

# ---------- Cards agrupados + prévia única ----------
check('card_admin("Ícones"' in TELA, "card Ícones existe (recolhível)")
check("Ícone da aba do navegador" in TELA and "f_icone" in TELA,
      "card Ícones reúne favicon + ícone do sistema lado a lado")
check('card_admin("Configurações de cores"' in TELA and "Botões e cards" not in TELA,
      "card único Configurações de cores (sem subtítulo redundante)")
check('"Testar conexão SMTP", "mail", testar_smtp' in TELA
      and '"Limpar TODOS os logs", "delete_forever"' in TELA,
      "ações extras no rodapé padrão dos cards (E-mail/Obs)")
check('", tipo="perigo"' not in TELA and '", tipo="secundario"' not in TELA,
      "sem variantes semânticas nos usos (tudo no padrão primário)")
check("pos_acao=remover_fav" in TELA,
      "restore dos Ícones no rodapé cobre sistema + aba")
check('columns="grid-cols' not in TELA,
      "nenhum grid com Tailwind no parâmetro columns (padrão Módulo)")
check('"Título da tela de login"' in TELA
      and '_campo_empilhado(\n "Título da tela de login"' not in TELA,
      "textos com rótulo dentro do input")
check("previa.refresh()" in TELA and "b_tam" in TELA,
      "prévia única ao vivo inclui botões/tamanho")
check("c_fundo" in TELA and "c_texto" in TELA,
      "prévia inclui fundo/texto dos cards")

# ---------- Anti-zeramento + restore dos Textos ----------
check("def _v(chave_estado" in TELA, "helper _v() existe (anti-zeramento)")
check("restaurargrupo(" not in TELA, "sem chamada a restaurargrupo (NameError)")
check("texto_login_título" not in TELA and "texto_home_subtítulo" not in TELA,
      "restore dos Textos sem chaves com acento")
check('set_config(k, _v(k, k, ""))' in TELA, "textos salvos via _v (sem zerar)")

# ---------- cor_fundo aplicado de verdade ----------
check('.q-page' in LAYOUT and 'cor_fundo' in LAYOUT,
      "layout pinta body + .q-page com cor_fundo")
check('get_config("cor_fundo"' in MAIN and "bg-blue-grey-10" not in MAIN,
      "/login lê cor_fundo (sem hardcoded)")

# ---------- Mínimo 2 colunas em todos os cards ----------
check('backup_interval_hours' in TELA and 'sessao_retencao' in TELA
      and 'Intervalo de backup (horas)' in TELA
      and 'Retenção de sessão (dias)' in TELA,
      "backup/retenção presentes (card gerais via card_config)")
check('columns="grid-cols-1 sm:grid-cols-2"' not in TELA,
      "grids do Config com mínimo 2 colunas (sem empilhar em 1)")
check('columns="grid-cols-2")' in TELA or 'grid-cols-2 md:grid-cols-3' in TELA,
      "cards usam grid-cols-2 de base")
check('grid-cols-1 sm:grid-cols-2 md:grid-cols-4' in TELA,
      "Cores com 4 colunas pares no desktop (4+4)")
check("max-sm:grid-cols-1" not in ler("mod_intranet/tema_modulo.py"),
      "bloco_aparencia sem colapso para 1 coluna")
check('label="Enviar arquivo .ico"' in TELA
      and "_linha_fav" not in TELA,
      "favicon inline (input + restaurar + upload, sem status)")
# ---------- Avisos configuráveis ----------
check("def notificar(" in TEMA and "def notificacao_timeout(" in TEMA,
      "helpers notificar/notificacao_timeout existem")
check('kwargs.pop("type"' in TEMA,
      "notificar aceita type= explícito (sem cair no fallback)")
check("ui.timer(1.0, lambda: ui.navigate.reload(), once=True)" in TELA,
      "Aplicar recarrega após 1 segundo (toast legível)")
for rel in ("main.py", "mod_intranet/telas.py",
            "mod_intranet/dialogo_backup.py",
            "mod_intranet/tela_configuracoes.py"):
    src = ler(rel)
    check("ui.notify(" not in src, f"{rel.split('/')[-1]} sem ui.notify direto")
check("notificacao_timeout" in TELA and "aviso_timeout" in TELA,
      "tempo de avisos editável nos Gerais (salvar/restore)")
check("_mudou_cor(" in TELA and "_alertar_restart" in TELA,
      "alerta único de restart ao trocar cor")
check("_nivel_depois != _nivel_antes or _otel_depois != _otel_antes" in TELA,
      "teste de logs só roda se nível mínimo/Loki mudaram")

# ---------- Runtime: timeout com clamp + restore do banco ----------
from mod_intranet.bd_conexao import init_db, get_config, set_config
from mod_intranet.tema_modulo import (
    notificacao_timeout, ler_cartao, estilo_cartao,
)
from mod_intranet.otel_integracao import obter_endpoint
from mod_intranet.grafana_sync import obter_grafana_url

init_db()
_orig_to = get_config("notificacao_timeout", "10")
try:
    set_config("notificacao_timeout", "10")
    check(notificacao_timeout() == 10, "timeout padrão = 10s")
finally:
    set_config("notificacao_timeout", _orig_to)
try:
    set_config("notificacao_timeout", "5")
    check(notificacao_timeout() == 5, "timeout configurável (5s)")
    set_config("notificacao_timeout", "99")
    check(notificacao_timeout() == 30, "timeout limitado a 30s")
    set_config("notificacao_timeout", "0")
    check(notificacao_timeout() == 1, "timeout mínimo 1s")
    set_config("notificacao_timeout", "abc")
    check(notificacao_timeout() == 10, "timeout inválido volta ao padrão (10s)")
finally:
    set_config("notificacao_timeout", _orig_to)

_orig_cf = get_config("intranet_cor_fundo_card", "#FFFFFF")
_orig_ct = get_config("intranet_cor_texto_card", "")
try:
    set_config("intranet_cor_fundo_card", "#FFFFFF")
    set_config("intranet_cor_texto_card", "")
    check(ler_cartao() == {"cor_fundo_card": "#FFFFFF", "cor_texto_card": ""},
          "ler_cartao com padrões")
    check("background-color:#FFFFFF;" in estilo_cartao(),
          "estilo_cartao pinta fundo do card")
finally:
    set_config("intranet_cor_fundo_card", _orig_cf)
    set_config("intranet_cor_texto_card", _orig_ct)
check(obter_endpoint() == "localhost:4317", "endpoint OTLP padrão local")
check(obter_grafana_url() == "http://localhost:3000", "URL Grafana padrão")
for k in ("intranet_cor_botao", "intranet_cor_texto_botao",
          "intranet_btn_tamanho", "intranet_cor_fundo_card",
          "notificacao_timeout"):
    check(get_config(k, "<ausente>") != "<ausente>", f"seed {k} existe")

print(f"RESULTADO: {_OK} OK, {_TOTAL - _OK} falha(s) "
      f"de {_TOTAL} verificações")
sys.exit(0 if _OK == _TOTAL else 1)
