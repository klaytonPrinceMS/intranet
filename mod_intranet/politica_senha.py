"""Política de senha do sistema: medidor, aceite de risco e tentativas de login.

O que este módulo responde, e o que ele **não** faz:

1. **Medidor de dificuldade** — mostra quão forte a senha é, mesmo quando ela
   já vazou. Vazamento e dificuldade são coisas diferentes: `123456` vaza e é
   fraca, mas a dificuldade é o que mede o trabalho de ataque.

2. **Aceite de risco com dupla confirmação** — o servidor que escolhe uma senha
   fraca ainda pode usá-la. O que muda é que ele **assina, sabendo**: um
   checkbox que ele tem de marcar consciously, e a confirmação de que entendeu.

3. **Tentativas de login** — limite configurável (3 por padrão), **sem travar a
   conta**: quem erra espera mais, até 30 segundos. Não é "fraco" por omissão:
   é a decisão de quem usa o sistema, porque bloqueio por tentativas muda um
   servidor que esqueceu a senha em mais um número no DTI — e a prefeitura
   tem gente que entra cinco vezes ao dia.

**Por que o aceite é só aviso, e não bloqueio.** Decisão de 30/09/2026 do
responsável: o aceite **registra e audita**, não impede promoção de perfil.
Isso não é esquecimento de segurança — é a posição de que a **
responsabilidade é do servidor que escolheu a senha fraca**, e ela se prova no
registro e na auditoria, não num trinco que o próprio sistema aplicaria contra
quem ele atendeu. O que o sistema garante é o **dever do controlador**: ter
medidas de segurança (Art. 6º, VI e VII, e Art. 46 da LGPD). O que ele não pode
garantir em nome do servidor é a senha boa dele, e fingir que garante —
impedindo o cargo — seria substituir o consentimento Fiscal pela decisão do
software.

O texto do aceite reproduz, em português claro, o que a lei diz e o que a lei
não diz. Ver `TEXTO_ACEITE_RISCO`.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Tentativas de login (30/09/2026, decisão do responsável).
TENTATIVAS_PADRAO = 3
TENTATIVAS_MINIMO = 3
TENTATIVAS_MAXIMO = 20
ATRASO_INICIAL_SEG = 1.0
ATRASO_MAXIMO_SEG = 30.0
PASSO_ATRASO_SEG = 1.5
JANELA_TENTATIVAS_SEG = 900  # 15 min: após isso a contagem zera

CHAVE_TENTATIVAS = "login_tentativas_maximas"
CHAVE_ATRASO_MAXIMO = "login_atraso_maximo_seg"

# Faixas do medidor. Os limites são de bits TOTAIS (comprimento x entropia),
# e não de "caracteres especiais": uma senha de 20 caracteres sorteados vale
# mais do que uma de 10 com símbolos. Ver `validador_senha._entropia`.
# --- PISO DE FORÇA: abaixo disto a senha não é usável (30/09/2026) ---
# Decisão do responsável: **0,5** da barra é o corte. Abaixo disso a senha
# simplesmente não pode ser usada — sem aceite, sem exceção, sem saída. O
# aceite de risco deixou de ser para senha fraca e passou a ser para senha
# BOA COM RISCO: passa de 0,5, mas aparece em vazamento, ou tem palavra do
# órgão, ou tem ano, ou tem o nome do usuário.
#
# Isso inverte o desenho anterior, e a inversão é o ponto: antes a pessoa podia
# aceitar uma senha de 15 bits. Agora o sistema recusa, e o que ela pode
# aceitar é o risco residual de uma senha decente.
FORCA_MINIMA = 0.5

# Piso de 75 bits para "Muito forte" é ALTÍSSIMO para senha humana: uma senha
# de 20 caracteres bem variados dá ~76. Colocar o patamar em 75 fazia quase toda
# senha boa cair no topo e a barra deixar de distinguir. Os pisos medem o que o
# validador considera aceitável (45 = "aceitável", 60 = "boa"), e o topo fica
# como elogio para o que é sorteado de verdade — não como rótulo de rotina.
FAIXAS = (
    (0, "muito_fraca", "Muito fraca", "negative"),
    (30, "fraca", "Fraca", "negative"),
    (45, "media", "Média", "warning"),
    (60, "forte", "Forte", "positive"),
    (90, "muito_forte", "Muito forte", "positive"),
)

# Cor da BARRA por faixa de força (0 a 1) — decisão do responsável, 30/09/2026.
#
# Mora aqui, e não na tela, pelo mesmo motivo de `FORCA_MINIMA`: o corte da
# cor é o mesmo corte que decide se a senha pode ser usada. Se a barra
# pintasse de verde a 0,45 — enquanto o sistema recusa por estar abaixo de
# 0,5 —, a tela estaria dizendo "vá em frente" na cor de quem aprova.
#
# | faixa         | cor         | leitura                               |
# |:--------------|:------------|:--------------------------------------|
# | abaixo de 0,5 | `negative`  | vermelho — não pode ser usada         |
# | 0,5 até 0,7   | `warning`   | amarelo — dá para usar, mas não é forte|
# | acima de 0,7  | `positive`  | verde — forte                         |
#
# O amarelo é a faixa em que a senha passa do corte e ainda não é forte, que é
# também a faixa em que costuma aparecer o risco residual e o aceite. As três
# cores são as do Quasar (`negative`/`warning`/`positive`), e é por isso que a
# faixa é a mesma das cinco faixas de RÓTULO acima — uma tela com duas
# palettes de cor discordando entre si seria pior que nenhuma.
FORCA_FORTE = 0.7
COR_BARRA_FRACA = "negative"   # < FORCA_MINIMA — não pode ser usada
COR_BARRA_MEDIA = "warning"    # >= FORCA_MINIMA e < FORCA_FORTE
COR_BARRA_FORTE = "positive"   # >= FORCA_FORTE

# Papéis que o aceite NÃO impede (decisão: aviso e registro, sem bloqueio).
PERFIS_ADMIN = ("administrador_geral", "administrador_modulo")


# ---------------------------------------------------------------------------
#  Medidor de dificuldade
# ---------------------------------------------------------------------------
def classificar(bits: float) -> tuple[str, str, str]:
    """`(chave, rótulo, cor)` a partir dos bits totais de entropia.

    A varredura vai do maior piso para o menor e **para na primeira casada**,
    porque `FAIXAS` está em ordem crescente: percorrer de cima para baixo dá
    o patamar mais alto que a senha alcança, que é a única leitura certa.
    Percorrendo de baixo para cima, o laço nunca saía do primeiro item — e tudo
    era "Muito fraca", qualquer que fosse a senha. Era o bug que a prova
    pegou: 70 bits saíam como "muito fraca".
    """
    try:
        v = float(bits or 0)
    except Exception:
        v = 0.0
    for piso, chave, rotulo, cor in reversed(FAIXAS):
        if v >= piso:
            return chave, rotulo, cor
    chave, rotulo, cor = FAIXAS[0][1:]
    return chave, rotulo, cor


def forca(medidor: dict) -> float:
    """A força como fração de 0 a 1 — a mesma escala da barra na tela."""
    try:
        return max(0.0, min(1.0, float((medidor or {}).get("percentual", 0)) / 100.0))
    except Exception:
        return 0.0


def acima_do_piso(medidor: dict) -> bool:
    """A senha passa do piso de 0,5? Abaixo disso ela não é usável."""
    try:
        return forca(medidor) >= FORCA_MINIMA
    except Exception:
        return False


def cor_da_barra(medidor: dict) -> str:
    """A cor da barra de força para este medidor (nome de cor do Quasar).

    Três faixas e nenhum critério novo: o corte é o mesmo `FORCA_MINIMA` que
    decide se a senha pode ser usada, e o topo é `FORCA_FORTE`. Ver o quadro
    nas constantes — o ponto é que a cor e a regra não podem divergir.
    """
    try:
        f = forca(medidor)
        if f < FORCA_MINIMA:
            return COR_BARRA_FRACA
        if f < FORCA_FORTE:
            return COR_BARRA_MEDIA
        return COR_BARRA_FORTE
    except Exception:
        return COR_BARRA_FRACA


def medidor(senha: str) -> dict:
    """O medidor completo: bits, faixa, rótulo, cor e barra.

    Usa o `validador_senha` já pronto — não repete regra de força aqui. O que
    este módulo acrescenta é a **faixa visual** e a leitura que responde "mas
    ela vazou e eu ainda assim…": vazamento é um aviso independente da
    dificuldade, e os dois aparecem juntos na tela.
    """
    try:
        from mod_intranet.validador_senha import analisar_offline
        r = analisar_offline(senha or "", "")
        bits = float(r.get("bits") or 0.0)
        chave, rotulo, cor = classificar(bits)
        # A barra é a fração do bits contra o topo da escala (100). Não usa
        # `nivel` do validador: o medidor é contínuo, e o usuário precisa ver
        # que está perto de um patamar, não só "média" ou "forte".
        return {
            "bits": round(bits, 1),
            "nivel": chave,
            "rotulo": rotulo,
            "cor": cor,
            "percentual": max(2, min(100, int(bits))),
            "vazou": bool(r.get("vazou")),
            "bloqueios": list(r.get("bloqueios") or []),
        }
    except Exception:
        logger.exception("politica_senha: medidor falhou")
        return {"bits": 0.0, "nivel": "muito_fraca", "rotulo": "Muito fraca",
                "cor": "negative", "percentual": 2, "vazou": False,
                "bloqueios": []}


# ---------------------------------------------------------------------------
#  Tentativas de login: atraso progressivo, sem travar a conta
# ---------------------------------------------------------------------------
def _config(chave: str, padrao) -> str:
    try:
        from mod_intranet.bd_conexao import get_config
        return str(get_config(chave, str(padrao)) or padrao)
    except Exception:
        return str(padrao)


def tentativas_maximas() -> int:
    """O limite, sempre entre 3 e 20 — 3 é o piso, por decisão do responsável.

    O piso de 3 não é o valor mais empedido de ataque: é o valor em que a
    pessoa comum erra duas vezes e acerta na terceira, e ainda não cai na
   partisan do "segurança" só no papel.
    """
    try:
        v = int(float(_config(CHAVE_TENTATIVAS, TENTATIVAS_PADRAO)))
    except Exception:
        return TENTATIVAS_PADRAO
    return max(TENTATIVAS_MINIMO, min(TENTATIVAS_MAXIMO, v))


def atraso_maximo_seg() -> float:
    try:
        return max(1.0, min(ATRASO_MAXIMO_SEG,
                            float(_config(CHAVE_ATRASO_MAXIMO,
                                          ATRASO_MAXIMO_SEG))))
    except Exception:
        return ATRASO_MAXIMO_SEG


def calcular_atraso(falhas: int) -> float:
    """Quanto esperar, em segundos, por `falhas` tentativas erradas.

    Linear por rampa, com teto: 0 falhas → 0 s; 1 → 1 s; 2 → 2,5 s; 3 → 4 s;
    e a partir daí sobe até o teto configurado. Sem teto, uma senha muito
    usada seria respondida em minutos — e o atacante não ganha com isso, só
    desacelera de menos.

    O efeito real do limite não é o tempo: é o **custo**. O login responde
    sempre "Usuário ou senha inválidos", sem dizer qual dos dois falhou, e a
    espera cresce a cada erro. Um ataque de dicionário fica caro sem nunca
    fechar a conta de quem só esqueceu a senha.
    """
    try:
        n = max(0, int(falhas))
        if n == 0:
            return 0.0
        bruto = ATRASO_INICIAL_SEG + PASSO_ATRASO_SEG * (n - 1) ** 1.5
        return round(min(bruto, atraso_maximo_seg()), 1)
    except Exception:
        return 0.0


def texto_atraso(seg: float) -> str:
    """O aviso que o login mostra quando vai demorar."""
    try:
        s = float(seg or 0)
    except Exception:
        return ""
    if s < 1:
        return ""
    if s < 60:
        return (f"Muitas tentativas incorretas. Aguarde {int(round(s))} "
                "segundo(s) antes de tentar de novo.")
    m = int(s // 60)
    return (f"Muitas tentativas incorretas. Aguarde {m} minuto(s) antes de "
            "tentar de novo.")


# ---------------------------------------------------------------------------
#  Estado das tentativas (tb_login_tentativas, no banco do módulo usuários)
# ---------------------------------------------------------------------------
def registrar_falha(user_nome: str) -> int:
    """Soma uma falha e devolve o total na janela. Devolve 0 se falhar.

    Falha aqui **não** pode derrubar o login: o registro serve para atrasar e
    auditar, e perder a contagem só faz o atacante ganhar tempo — nunca faz o
    servidor legítimo ser barrado.
    """
    try:
        from mod_intranet import autenticacao
        gest = autenticacao._gest()
        if gest is None:
            return 0
        return int(gest.registrar_tentativa_login(user_nome) or 0)
    except Exception:
        logger.exception("politica_senha: não foi possível registrar a falha "
                         "de login; seguindo sem contagem")
        return 0


def zerar_tentativas(user_nome: str) -> bool:
    """Login certo zera a contagem da janela."""
    try:
        from mod_intranet import autenticacao
        gest = autenticacao._gest()
        if gest is None:
            return False
        return bool(gest.zerar_tentativas_login(user_nome))
    except Exception:
        logger.exception("politica_senha: não foi possível zerar as "
                         "tentativas de login")
        return False


def tentativas_de(user_nome: str) -> int:
    """Quantas falhas há na janela agora."""
    try:
        from mod_intranet import autenticacao
        gest = autenticacao._gest()
        if gest is None:
            return 0
        return int(gest.tentativas_login(user_nome) or 0)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
#  O texto do aceite — LGPD
# ---------------------------------------------------------------------------
# Escrito para o SERVIDOR ler, não para o jurídico. A lei aparece pelo que ela
# de fato estabelece, e — tão importante quanto isso — pelo que ela NÃO
# estabelece. Um texto de aceite que só cita artigo para assustar é propaganda,
# não informação, e a prefeitura não pode fazer isso com servidor público.
TEXTO_ACEITE_RISCO_EN = """\
By checking the box, you take responsibility for this access and for its use.

You are aware that:

1. The chosen password appears in known public breaches and can be guessed by
   attack. With it, whoever obtains it can read, change and delete what is
   under your profile — including other people's data.

2. The municipality is the DATA CONTROLLER of the personal data handled here
   and adopts security measures to protect it. This follows Brazilian Law
   13.709/2018 (LGPD), in particular Art. 6º, VI and VII (security and
   prevention) and Art. 46, which requires technical and administrative
   measures against unauthorized access.

3. The CO-RESPONSIBILITY is yours. The law does not transfer to the system the
   task of guessing your password: choosing an easy password is your own act,
   and the consequences for your profile are yours.

4. If your account is breached through a weak or leaked password, improper use
   will be attributed to your profile — not to the municipality, which
   advises and offers a password change at any time.

5. You may change this password whenever you want, at any time, without
   justification."""

# O que a PESSOA lê na tela. Só PT-BR: mostrar os dois idiomas empilhados
# duplicava o texto na tela e empurrava o botão para fora de vista — e o texto
# em inglês não ia fazer sentido para servidor de prefeitura nenhuma.
TEXTO_ACEITE_RISCO = """\
Ao marcar a caixa, você assume a responsabilidade por este acesso e pelo uso
que for feito com ele.

Você está ciente de que:

1. A senha escolhida aparece em vazamentos públicos conhecidos e pode ser
   deduzida por ataque. Com ela, quem a obtiver pode ler, alterar e apagar o
   que está sob o seu perfil — inclusive dados de outros servidores.

2. A prefeitura é a CONTROLADORA dos dados pessoais aqui tratados e adota
   medidas de segurança para protegê-los. Isso decorre da Lei nº 13.709/2018
   (LGPD), em especial do Art. 6º, VI e VII (segurança e prevenção) e do
   Art. 46, que exige medidas técnicas e administrativas contra acessos não
   autorizados.

3. A CO-RESPONSABILIDADE é sua. A lei não transfere ao sistema a tarefa de
   adivinhar a sua senha: escolher senha fácil é ato seu, e as consequências
   sobre o seu perfil são suas.

4. Se a sua conta for invadida por senha fraca ou vazada, o uso indevido
   será atribuído ao seu perfil — e não à prefeitura, que orienta e oferece
   troca de senha a qualquer momento.

5. Você pode trocar esta senha quando quiser, em qualquer momento, sem
   justificar."""