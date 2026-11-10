# -*- coding: utf-8 -*-
"""Libera espaço no celular apagando SOMENTE arquivos que já têm cópia idêntica no backup.

Uso:
  python limpar_verificado.py --destino "D:\\Backup celular" --origem /sdcard/DCIM/Camera [--origem ...]
                              [--dias 30] [--hash] [--aplicar]

  --destino   a MESMA pasta usada no backup_midias.py
  --origem    pasta do celular a limpar (pode repetir)
  --dias N    mantém no celular os arquivos modificados nos últimos N dias (padrão 30; 0 = apaga todos os conferidos)
  --incluir-ocultos  também considera miniaturas, status e lixeira (só se o backup foi feito com essa opção)
  --hash      compara tamanho + MD5 de cada arquivo (bem mais lento; use quando o backup não foi feito pelo
              backup_midias.py e por isso as datas dos arquivos não batem)
  --aplicar   apaga de verdade. Sem ele, só gera o plano (lista, contagem e GB) e não toca em nada.

Regras de proteção (não dá para desligar):
  - só apaga dentro do armazenamento interno (/sdcard), nunca a raiz inteira;
  - recusa pastas de backup de conversas (WhatsApp/Databases, WhatsApp/Backups), Android/data e Android/obb;
  - um arquivo só entra na lista se a cópia existir no destino com o mesmo tamanho e a mesma data de
    modificação (ou o mesmo MD5, com --hash);
  - a conferência é refeita na hora de apagar: nada vem de listas antigas.

Atenção para mídias do WhatsApp/Telegram: depois de apagadas, as conversas mostram a miniatura mas o arquivo
não abre mais no celular (fica só no backup). Avise o dono antes.
"""
import datetime
import hashlib
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _adb  # noqa: E402
import _midias as M  # noqa: E402

_adb.utf8_stdout()
_adb.ajuda(__doc__)
argv = sys.argv[1:]


def valores(nome):
    return [argv[i + 1] for i, a in enumerate(argv) if a == nome and i + 1 < len(argv)]


if not valores("--destino") or not valores("--origem"):
    print(__doc__)
    sys.exit(1)
DEST = _adb.caminho_local(valores("--destino")[0])
DIAS = int((valores("--dias") or ["30"])[0])
HASH = "--hash" in argv
APLICAR = "--aplicar" in argv
OCULTOS = "--incluir-ocultos" in argv   # mesma regra do backup: miniaturas, status e lixeira ficam de fora
PROIBIDO = re.compile(r"^/sdcard/?$|^/sdcard/Android/(data|obb)(/|$)|/WhatsApp( Business)?/(Databases|Backups)(/|$)|"
                      r"/Telegram/(Telegram Files/)?\.?tdata", re.I)

if not os.path.isdir(DEST):
    sys.exit(f"Destino não encontrado: {DEST}. Conecte o disco do backup.")
origens = []
for o in valores("--origem"):
    n = M.normalizar(o)
    if not n.startswith("/sdcard/") or PROIBIDO.search(n) or n.count("/") < 2:
        sys.exit(f"Origem recusada por segurança: {o}")
    origens.append(n)
_adb.require_device()
agora = _adb.device_now()
limite = agora - DIAS * 86400


def md5_local(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def lotes(caminhos, limite=3000):
    """Agrupa caminhos em comandos curtos (aparelhos antigos aceitam comandos de só ~4 KB pelo adb)."""
    atual, comp = [], 0
    for c in caminhos:
        n = len(_adb.q(c)) + 1
        if atual and comp + n > limite:
            yield atual
            atual, comp = [], 0
        atual.append(c)
        comp += n
    if atual:
        yield atual


def md5_aparelho(caminhos):
    res = {}
    for lote in lotes(caminhos):
        out = _adb.sh("md5sum " + " ".join(_adb.q(x) for x in lote) + " 2>/dev/null", timeout=3600)
        for ln in out.splitlines():
            m = re.match(r"^([0-9a-f]{32}) [ *](.+)$", ln)   # toybox: "hash  nome"; GNU: "hash *nome"
            if m:
                res[M.normalizar(m.group(2))] = m.group(1)
    return res


def planejar():
    plano, mantidos, sem_copia = [], 0, []
    por_origem = []
    for o in origens:
        itens = M.listar(o, incluir_ocultos=OCULTOS)
        dup = M.colisoes_maiusculas(itens)
        cand = []
        for p, (s, mt) in itens.items():
            if PROIBIDO.search(p):
                continue
            if DIAS and mt >= limite:
                mantidos += 1
                continue
            # sem --hash: tamanho + data de modificação; com --hash: tamanho + MD5 (a data não importa)
            ok_copia = (M.tamanho_local(M.local(DEST, p)) == s) if HASH else M.igual(M.local(DEST, p), s, mt)
            if ok_copia and p not in dup:
                cand.append((p, s))
            else:
                sem_copia.append(p)
        if HASH and cand:
            print(f"Calculando MD5 de {len(cand)} arquivos em {o} (aparelho e backup)...", flush=True)
            hs = md5_aparelho([p for p, _ in cand])
            ok = []
            for p, s in cand:
                if hs.get(p) and hs[p] == md5_local(M.local(DEST, p)):
                    ok.append((p, s))
                else:
                    sem_copia.append(p)
            cand = ok
        plano += cand
        por_origem.append((o, len(itens), len(cand), sum(s for _, s in cand)))
    return plano, mantidos, sem_copia, por_origem


print(f"Conferindo contra o backup em {DEST} (mantendo os últimos {DIAS} dias)...", flush=True)
plano, mantidos, sem_copia, por_origem = planejar()
os.makedirs(os.path.join(DEST, "_logs"), exist_ok=True)
carimbo = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
lista = os.path.join(DEST, "_logs", f"{'apagados' if APLICAR else 'plano_exclusao'}_{carimbo}.txt")
with open(lista, "w", encoding="utf-8") as f:
    for p, s in plano:
        f.write(f"{p}\t{s}\n")

print("\n| pasta | arquivos no celular | com cópia idêntica e mais antigos que o limite | a liberar |")
print("|---|---:|---:|---:|")
for o, n, k, b in por_origem:
    print(f"| {o} | {n} | {k} | {M.fmt_gb(b)} |")
total = sum(s for _, s in plano)
print(f"\nTotal: {len(plano)} arquivos, {M.fmt_gb(total)}. Ficam no celular: {mantidos} recentes e "
      f"{len(sem_copia)} sem cópia conferida.")
if any("whatsapp" in o.lower() or "telegram" in o.lower() for o in origens):
    print("Aviso: mídias apagadas do WhatsApp/Telegram deixam de abrir dentro das conversas (ficam só no backup).")
print(f"Lista: {lista}")
if not APLICAR:
    print("\nNada foi apagado (modo plano). Para apagar, repita com --aplicar após a autorização do dono.")
    sys.exit(0)

df_antes = _adb.sh("df -h /data | tail -1", timeout=30).strip()
print(f"\nApagando {len(plano)} arquivos...", flush=True)
t0, feitos = time.time(), 0
for i, lote in enumerate(lotes([p for p, _ in plano])):
    # cada caminho vai entre aspas simples; nada é interpretado pelo shell do aparelho
    _adb.adb("shell", "rm -f " + " ".join(_adb.q(p) for p in lote), timeout=600)
    feitos += len(lote)
    if i % 50 == 0 or feitos == len(plano):
        print(f"  {feitos}/{len(plano)} ({time.time() - t0:.0f} s)", flush=True)

# confere: nenhum arquivo do plano pode continuar existindo
restam = set()
for o in origens:
    restam |= set(M.listar(o, incluir_ocultos=True))
nao_apagados = [p for p, _ in plano if p in restam]
df_depois = _adb.sh("df -h /data | tail -1", timeout=30).strip()
print(f"\nApagados: {len(plano) - len(nao_apagados)} de {len(plano)}. Não apagados: {len(nao_apagados)}.")
for p in nao_apagados[:20]:
    print(f"  ainda existe: {p}")
print(f"Espaço /data antes : {df_antes}\nEspaço /data depois: {df_depois}")
print("A galeria e o WhatsApp atualizam sozinhos; se aparecer miniatura antiga, reinicie o aparelho.")
