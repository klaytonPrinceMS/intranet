"""EN: First-access phone flow — message phone, out-of-range warning, the two
gates and the 4-day temporary release.

PT-BR: Primeiro acesso — telefone de recado, aviso de número fora da faixa, as
DUAS travas e a liberação temporária de 4 dias.

POR QUE PLAYWRIGHT E NÃO O CONSOLE DO NAVEGADOR
    O NiceGUI liga os handlers no `v-model` do Vue. Um evento sintético
    (`new Event('input')`, `.click()` por JavaScript) NÃO chega lá — e foi
    assim que o aviso de faixa pareceu quebrado quando estava certo: o
    evento nunca saiu do navegador. Aqui `fill()` e `click()` são de verdade,
    o mesmo caminho que o dedo da pessoa percorre.

O QUE ESTE TESTE PROVA
    1. o diálogo de telefones abre e tem o campo de recado;
    2. número fora das faixas mostra o aviso E a faixa mais próxima;
    3. número dentro das faixas não mostra aviso;
    4. sem telefone da prefeitura, a PRIMEIRA trava aparece e nada é salvo;
    5. a SEGUNDA trava escreve o preço (4 dias, bloqueio, DTI);
    6. confirmar as duas libera por prazo, com o bilhete na tela;
    7. no banco: particular fica FORA da lista, pendência baixa, prazo ≤ 4 dias.

Executa: .venv/bin/python assets/test/test_primeiro_acesso_e2e.py
Requer o servidor no ar em http://localhost:8080.
"""
import os
import re
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAIZ = os.path.dirname(RAIZ) if os.path.basename(RAIZ) == "assets" else RAIZ
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

BASE = "http://localhost:8080"
USUARIO = "TESTE_E2E_TEL"
SENHA_PROV = "123456"
SENHA_NOVA = "SenhaE2E9"

_OK = 0
_FALHAS = []


def check(cond, msg):
    global _OK
    if cond:
        _OK += 1
        print(f"  ok   {msg}")
    else:
        _FALHAS.append(msg)
        print(f"  FALHA {msg}")


def _rodar_py(codigo):
    """Roda um trecho Python no projeto, sem deixar arquivo para trás."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as f:
        f.write(codigo)
        caminho = f.name
    try:
        return subprocess.run([".venv/bin/python", caminho],
                              capture_output=True, text=True, timeout=120).stdout
    finally:
        os.unlink(caminho)


def preparar():
    saida = _rodar_py(f'''
import sys
sys.path.insert(0, {RAIZ!r})
from mod_gest_cad_usuario import bd_manipulador as bd
from mod_intranet import autenticacao as a
n = {USUARIO!r}
c = bd.get_connection()
for t in ("tb_telefone_usuario", "tb_acesso_usuario", "tb_usuarios"):
    c.execute(f"DELETE FROM {{t}} WHERE user_nome=?", (n,))
c.commit(); c.close()
bd.criar_usuario("e2e", n, {SENHA_PROV!r}, nome_completo="Coleta Municipal E2E")
a.trocar_senha_propria(n, {SENHA_PROV!r}, {SENHA_NOVA!r})
a.marcar_trocar_senha(n, False)
print("OK")
''')
    return "OK" in saida


def limpar():
    _rodar_py(f'''
import sys
sys.path.insert(0, {RAIZ!r})
from mod_gest_cad_usuario import bd_manipulador as bd
c = bd.get_connection()
for t in ("tb_telefone_usuario", "tb_acesso_usuario", "tb_usuarios"):
    c.execute(f"DELETE FROM {{t}} WHERE user_nome=?", ({USUARIO!r},))
c.commit(); c.close()
''')


def estado():
    return _rodar_py(f'''
import sys
sys.path.insert(0, {RAIZ!r})
from mod_gest_cad_usuario import bd_manipulador as bd
n = {USUARIO!r}
pub = [t[2] for t in bd.listar_telefones(n, apenas_empresa=True)]
info = bd.informacao_acesso_provisorio(n)
todos = [(t[2], t[3], t[4], t[6], t[7]) for t in bd.listar_telefones(n)]
print("PUBLICOS=" + ",".join(pub))
print("TODOS=" + repr(todos))
print("PROVISORIO=" + str(info["provisorio"]))
print("DIAS=" + str(info["dias_restantes"]))
print("PENDENTE=" + str(bd.telefone_pendente(n)))
''')


def _campo(dlg, rotulo):
    """O input de um rótulo do diálogo — pelo texto do label, não por índice,
    porque a ordem dos campos não é contrato."""
    return dlg.get_by_label(rotulo, exact=True)


def rodar():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page()
        try:
            pagina.goto(f"{BASE}/login", wait_until="load")
            pagina.get_by_label("Usuário").fill(USUARIO)
            pagina.get_by_label("Senha").fill(SENHA_NOVA)
            pagina.get_by_role("button", name="Entrar").click()
            pagina.wait_for_url(f"{BASE}/", timeout=25000)

            dlg = pagina.locator(".q-dialog")
            dlg.wait_for(state="visible", timeout=25000)
            check(dlg.get_by_text("Seus telefones").is_visible(),
                  "1. o diálogo de telefones abriu")
            check(dlg.locator("[data-testid=primeiro-acesso-chk-recado]").is_visible(),
                  "1. a opção de telefone de recado está na tela")
            check(_campo(dlg, "Celular particular").count() > 0
                  and _campo(dlg, "Celular da prefeitura").count() > 0
                  and _campo(dlg, "Telefone fixo da prefeitura").count() > 0
                  and _campo(dlg, "Telefone residencial (opcional)").count() > 0,
                  "1. os quatro campos de telefone estão presentes")

            # 2) fora da faixa -> aviso com a faixa mais proxima
            _campo(dlg, "Telefone fixo da prefeitura").fill("0035999999")
            aviso = dlg.locator(".text-orange-8")
            aviso.wait_for(state="visible", timeout=10000)
            texto_aviso = aviso.inner_text()
            check("fora das faixas" in texto_aviso,
                  f"2. aviso de fora da faixa: {texto_aviso[:60]}...")
            check("faixa mais próxima" in texto_aviso,
                  "2. o aviso diz qual é a faixa mais próxima")

            # 3) dentro da faixa -> sem aviso
            _campo(dlg, "Telefone fixo da prefeitura").fill("0035915150")
            pagina.wait_for_timeout(1500)
            # o aviso é LIMPADO (set_text("")), não removido do DOM — o
            # elemento continua lá, vazio. Conferir `count() == 0` daria
            # falso negativo e foi exatamente o que aconteceu na primeira
            # versão deste teste.
            aviso_texto = (dlg.locator(".text-orange-8").inner_text()
                           if dlg.locator(".text-orange-8").count() else "")
            check("fora das faixas" not in aviso_texto,
                  f"3. número dentro da faixa limpa o aviso (restou: {aviso_texto!r})")

            # 4) sem telefone da prefeitura -> PRIMEIRA trava
            _campo(dlg, "Telefone fixo da prefeitura").fill("")
            _campo(dlg, "Celular particular").fill("00988881111")
            pagina.wait_for_timeout(400)
            dlg.get_by_role("button", name="Salvar telefones").click()
            trava1 = pagina.get_by_text("Falta um telefone da prefeitura")
            trava1.wait_for(state="visible", timeout=15000)
            check(trava1.is_visible(),
                  "4. PRIMEIRA trava: o sistema pediu o telefone da prefeitura")
            check(pagina.get_by_role("button",
                                     name="Informar o telefone do setor").is_visible(),
                  "4. a primeira trava oferece voltar e informar o do setor")
            est = estado()
            check("PENDENTE=True" in est,
                  "4. nada foi gravado: a pendência continua ligada")

            # 5) SEGUNDA trava: o preco escrito
            pagina.get_by_role("button", name="Não sei meu número").click()
            trava2 = pagina.get_by_text("Acesso temporário")
            trava2.wait_for(state="visible", timeout=15000)
            check(trava2.is_visible(), "5. SEGUNDA trava apareceu")
            corpo = pagina.locator(".q-card").filter(
                has_text="Acesso temporário").first.inner_text()
            check("4 dias" in corpo, "5. a segunda trava escreve o prazo de 4 dias")
            check("DTI" in corpo, "5. a segunda trava diz que só o DTI reabre")
            check(pagina.get_by_role(
                "button", name="Voltar e informar o número").is_visible(),
                "5. a segunda trava ainda deixa voltar")

            # 6) confirmar as duas -> liberacao por prazo + bilhete
            pagina.get_by_role(
                "button", name="Entendo, liberar por enquanto").click()
            bilhete = pagina.get_by_text("Acesso liberado por enquanto")
            bilhete.wait_for(state="visible", timeout=15000)
            check(bilhete.is_visible(), "6. bilhete da liberação temporária")
            texto_bilhete = pagina.locator(".q-card").filter(
                has_text="Acesso liberado por enquanto").first.inner_text()
            check("4 dias" in texto_bilhete, "6. o bilhete repete o prazo")
            check("sem número" in texto_bilhete,
                  "6. o bilhete avisa que a lista fica sem número")

            # 7) o que ficou no banco
            est = estado()
            check("PROVISORIO=True" in est, "7. a conta ficou em liberação provisória")
            dias = int(re.search(r"DIAS=(\d+)", est).group(1))
            check(0 <= dias <= 4, f"7. o prazo é de {dias} dia(s), no máximo 4")
            check("PENDENTE=False" in est,
                  "7. a pendência de telefone foi baixada")
            check("00988881111" not in est.split("PUBLICOS=")[1].split("\n")[0],
                  f"7. o particular NAO entra na lista (publicáveis: "
                  f"{est.split('PUBLICOS=')[1].split(chr(10))[0] or 'nenhum'})")
        finally:
            navegador.close()


def main():
    print("\n=== primeiro acesso: recado, faixas e as duas travas ===")
    try:
        if not preparar():
            print("  ERRO: não foi possível preparar a conta de teste")
            return 1
        rodar()
    except Exception as e:
        import traceback
        traceback.print_exc()
        _FALHAS.append(f"exceção: {e}")
    finally:
        limpar()
    print(f"\n{_OK} ok, {len(_FALHAS)} falha(s)")
    for f in _FALHAS:
        print(f"  - {f}")
    return 1 if _FALHAS else 0


if __name__ == "__main__":
    sys.exit(main())
