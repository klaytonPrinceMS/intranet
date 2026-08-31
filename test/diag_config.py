"""QA Diagnostico: fluxo salvar_configs -> reload -> ler valores.

Testa se set_config realmente persiste e se get_config retorna
os valores corretos em CONEXÕES DIFERENTES (simula reload de pagina).
"""
import sys, os, time, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mod_intranet.conexao_bd import get_config, set_config, get_connection

CHAVES_NUM = {
    "cotadisco_global_gb": ("10", "25"),
    "editpdf_lote_arquivos": ("10", "20"),
    "editpdf_lote_mb": ("1024", "2048"),
    "editpdf_usuario_gb": ("1", "5"),
    "editpdf_expiracao_min": ("10", "30"),
}
CHAVES_TXT = {
    "editpdf_texto_upload_titulo": ("Envie um ou mais PDFs", "Titulo Teste QA"),
    "editpdf_texto_header_sub": ("Reduza, junte, corte, divida e verifique seus documentos.", "Subtitulo QA"),
}

erros = []

def ok(msg):
    print(f"  [OK] {msg}")

def falha(msg):
    print(f"  [FALHA] {msg}")
    erros.append(msg)

print("=" * 60)
print("TESTE 1: set_config grava, get_config lê (mesma conexao logica)")
print("=" * 60)
for k, (padrao, novo) in CHAVES_NUM.items():
    set_config(k, padrao)
    v = get_config(k, "__FALTA__")
    if v == padrao:
        ok(f"{k} = {v} (padrao)")
    else:
        falha(f"{k}: esperava '{padrao}', veio '{v}'")
    set_config(k, novo)
    v = get_config(k, "__FALTA__")
    if v == novo:
        ok(f"{k} = {novo} (novo)")
    else:
        falha(f"{k}: esperava '{novo}', veio '{v}'")

print()
print("=" * 60)
print("TESTE 2: NOVA CONEXAO (simula reload de pagina)")
print("=" * 60)
for k, (padrao, novo) in CHAVES_NUM.items():
    set_config(k, novo)
for k, (padrao, novo) in CHAVES_TXT.items():
    set_config(k, novo)

# Fechar tudo e reabrir (forca nova conexao)
conn = get_connection()
conn.close()

for k, (_, novo) in CHAVES_NUM.items():
    v = get_config(k, "__FALTA__")
    if v == novo:
        ok(f"{k} = {novo} (persiste)")
    else:
        falha(f"{k}: esperava '{novo}', veio '{v}'")
for k, (_, novo) in CHAVES_TXT.items():
    v = get_config(k, "__FALTA__")
    if v == novo:
        ok(f"{k} = {novo} (persiste)")
    else:
        falha(f"{k}: esperava '{novo}', veio '{v}'")

print()
print("=" * 60)
print("TESTE 3: int(v or default) como o salvar_configs faz")
print("=" * 60)
for k, (_, novo) in CHAVES_NUM.items():
    raw = get_config(k, "0")
    resultado = max(1, int(raw or 10))
    if resultado == int(novo):
        ok(f"{k}: raw='{raw}' -> int={resultado}")
    else:
        falha(f"{k}: raw='{raw}' -> int={resultado}, esperava {int(novo)}")

print()
print("=" * 60)
print("TESTE 4: Simula salvar_configs EXATO (lê .value como float)")
print("=" * 60)
# NiceGUI ui.number retorna float. Simular:
simulacoes = {
    "cotadisco_global_gb": 25.0,    # usuario digita 25
    "editpdf_lote_arquivos": 20.0,
    "editpdf_lote_mb": 2048.0,
    "editpdf_usuario_gb": 5.0,
    "editpdf_expiracao_min": 30.0,
}
for k, val_float in simulacoes.items():
    gb_g = max(1, int(val_float or 10))
    set_config(k, gb_g)

# Recarrega (nova conexao)
conn = get_connection()
conn.close()

for k, val_float in simulacoes.items():
    esperado = int(val_float)
    v_raw = get_config(k, "0")
    v_int = max(1, int(v_raw or 10))
    if v_int == esperado:
        ok(f"{k}: float({val_float}) -> salvo={esperado} -> lido={v_int}")
    else:
        falha(f"{k}: float({val_float}) -> salvo={esperado} -> lido={v_int}")

print()
print("=" * 60)
print("TESTE 5: Simula valor vazio/None (o que NiceGUI pode retornar)")
print("=" * 60)
valores_problematicos = {
    "cotadisco_global_gb": None,
    "editpdf_lote_arquivos": 0,
    "editpdf_lote_mb": None,
}
for k, val in valores_problematicos.items():
    resultado = max(1, int(val or 10))
    print(f"  {k}: value={val} -> int({val or 10}) = {resultado}  (deveria ser 10=padrao)")

print()
print("=" * 60)
print("TESTE 6: Verifica se init_db_pdf() ou init_db() sobrescreve editpdf_ keys")
print("=" * 60)
# Grava valores unicos
for k, (_, novo) in CHAVES_NUM.items():
    set_config(k, novo)
print("  Valores gravados. Chamando init_db_pdf()...")
from mod_edit_pdf.manipulador_bd import init_db_pdf
init_db_pdf()
for k, (_, novo) in CHAVES_NUM.items():
    v = get_config(k, "__FALTA__")
    if v == novo:
        ok(f"{k} = {novo} (init_db_pdf NAO sobrescreveu)")
    else:
        falha(f"{k}: init_db_pdf SOBRESCREVEU para '{v}'!")

print()
print("=" * 60)
print("TESTE 7: Verifica se init_db() central sobrescreve editpdf_ keys")
print("=" * 60)
for k, (_, novo) in CHAVES_NUM.items():
    set_config(k, novo)
print("  Valores gravados. Chamando init_db() central...")
from mod_intranet.conexao_bd import init_db
init_db()
for k, (_, novo) in CHAVES_NUM.items():
    v = get_config(k, "__FALTA__")
    if v == novo:
        ok(f"{k} = {novo} (init_db NAO sobrescreveu)")
    else:
        falha(f"{k}: init_db SOBRESCREVEU para '{v}'!")

# Restaurar padrao
print()
print("=" * 60)
print("RESTAURANDO PADRAO")
print("=" * 60)
for k, (padrao, _) in CHAVES_NUM.items():
    set_config(k, padrao)
for k, (padrao, _) in CHAVES_TXT.items():
    set_config(k, padrao)
print("  Restaurado.")

print()
print("=" * 60)
if erros:
    print(f"RESULTADO: {len(erros)} FALHA(S)")
    for e in erros:
        print(f"  - {e}")
else:
    print("RESULTADO: TODOS OS TESTES OK")
print("=" * 60)
