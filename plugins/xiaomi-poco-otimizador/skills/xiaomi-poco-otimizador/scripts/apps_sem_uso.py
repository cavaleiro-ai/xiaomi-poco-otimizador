# -*- coding: utf-8 -*-
"""Lista apps sem uso há N dias (ou nunca abertos) a partir das estatísticas de uso do Android.
SOMENTE LEITURA.

Uso:
  python apps_sem_uso.py [--dias 60] [--incluir-sistema] [--coleta PASTA] [--saida arquivo.md]

  --dias N           limite de dias sem abrir (padrão 60)
  --incluir-sistema  inclui apps de sistema (candidatos a debloat); por padrão só os instalados pelo usuário
  --coleta PASTA     usa uma pasta gerada pelo coletar.py em vez do aparelho conectado
  --saida ARQ        grava a tabela em Markdown (e um .csv ao lado)

Coluna "sensível": apps de banco, carteiras de cripto, governo, autenticação, segurança ou empresa.
Esses NUNCA devem ser removidos sem confirmação item a item do dono, mesmo sem uso: alguns só são
abertos raramente (ex.: token do banco, FGTS) mas fazem falta na hora em que são necessários.
"""
import csv
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _adb  # noqa: E402

_adb.utf8_stdout()
_adb.ajuda(__doc__)


def arg(nome, padrao=None):
    return sys.argv[sys.argv.index(nome) + 1] if nome in sys.argv else padrao


DIAS = int(arg("--dias", 60))
SISTEMA = "--incluir-sistema" in sys.argv
COLETA = arg("--coleta")
SAIDA = arg("--saida")


def ler(rel):
    p = os.path.join(COLETA, rel)
    if not os.path.isfile(p):
        return ""
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read().replace("\r", "")


if COLETA:
    usage = ler("03_dumpsys/zz_usagestats.txt")
    pkgdump = ler("03_dumpsys/zz_package_all.txt")
    terc_txt = ler("07_apps/packages_third_party.txt")
    sist_txt = ler("07_apps/packages_system.txt")
    agora = None  # data da coleta: linha do 'date' em uname_id.txt (ex.: "Thu Nov  5 22:59:44 -03 2026")
    for ln in ler("00_identidade/uname_id.txt").splitlines():
        try:
            agora = datetime.datetime.strptime(" ".join(ln.split()[:4] + ln.split()[-1:]), "%a %b %d %H:%M:%S %Y")
        except (ValueError, IndexError):
            continue
    if agora is None:
        datas = re.findall(r'lastTimeUsed="(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)"', usage)
        agora = max(datetime.datetime.strptime(d, "%Y-%m-%d %H:%M:%S") for d in datas) if datas else datetime.datetime.now()
else:
    _adb.require_device()
    print("Lendo estatísticas de uso e pacotes do aparelho (1 a 3 minutos)...", flush=True)
    usage = _adb.sh("dumpsys usagestats", timeout=300)
    pkgdump = _adb.sh("dumpsys package packages", timeout=300)
    terc_txt = _adb.sh("pm list packages -3 -i", timeout=60)
    sist_txt = _adb.sh("pm list packages -s", timeout=60) if SISTEMA else ""
    try:
        agora = datetime.datetime.fromtimestamp(_adb.device_now())
    except (OverflowError, OSError, ValueError):
        agora = datetime.datetime.now()

instalador = {}
for ln in terc_txt.splitlines():
    m = re.match(r"package:(\S+)(?:\s+installer=(\S+))?", ln)
    if m:
        instalador[m.group(1)] = m.group(2) or "?"
pacotes = dict(instalador)
if SISTEMA:
    for ln in sist_txt.splitlines():
        m = re.match(r"package:(\S+)", ln)
        if m:
            pacotes.setdefault(m.group(1), "(sistema)")

ultimo, aberturas = {}, {}
for m in re.finditer(r'package=(\S+) totalTimeUsed="[^"]*" lastTimeUsed="(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)"(?:.*?appLaunchCount=(\d+))?', usage):
    p, d, n = m.group(1), m.group(2), m.group(3)
    if d >= "1980":
        dt = datetime.datetime.strptime(d, "%Y-%m-%d %H:%M:%S")
        if p not in ultimo or dt > ultimo[p]:
            ultimo[p] = dt
    if n:
        aberturas[p] = max(aberturas.get(p, 0), int(n))
janela = re.search(r'In-memory yearly stats\n\s*timeRange="([^"]+)"', usage)

inst = {}
for bloco in re.split(r"\n  Package \[", pkgdump):
    m = re.match(r"([^\]]+)\]", bloco)
    if not m:
        continue
    fi = re.search(r"firstInstallTime=(\d{4}-\d\d-\d\d)", bloco)
    if fi:
        inst[m.group(1)] = fi.group(1)

sensivel = _adb.categoria_sensivel   # lista única, compartilhada com restringir_segundo_plano.py


linhas = []
for p, ins in pacotes.items():
    u = ultimo.get(p)
    dias = (agora - u).days if u else None
    if dias is not None and dias < DIAS:
        continue
    linhas.append(dict(pacote=p, instalado=inst.get(p, "?"), ultimo_uso=u.strftime("%Y-%m-%d") if u else "nunca registrado",
                       dias_sem_uso=dias if dias is not None else "", aberturas=aberturas.get(p, 0), instalador=ins,
                       sensivel=sensivel(p)))
linhas.sort(key=lambda r: (r["dias_sem_uso"] != "", -(r["dias_sem_uso"] or 0)))

md = [f"# Apps sem uso há {DIAS}+ dias ({'inclui sistema' if SISTEMA else 'só instalados pelo usuário'})", ""]
if janela:
    md.append(f"Janela das estatísticas anuais do Android: {janela.group(1)}. 'Nunca registrado' = não foi aberto nessa janela.")
md.append(f"Data de referência: {agora:%Y-%m-%d}. Total: {len(linhas)} apps; "
          f"{sum(1 for r in linhas if r['sensivel'])} marcados como sensíveis (não remover sem confirmação item a item).")
md.append("")
md.append("| pacote | instalado em | último uso | dias sem uso | aberturas (ano) | instalador | sensível |")
md.append("|---|---|---|---:|---:|---|---|")
for r in linhas:
    md.append(f"| `{r['pacote']}` | {r['instalado']} | {r['ultimo_uso']} | {r['dias_sem_uso']} | {r['aberturas']} | "
              f"{r['instalador']} | {r['sensivel']} |")
print("\n".join(md))
if SAIDA:
    os.makedirs(os.path.dirname(os.path.abspath(SAIDA)), exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    csvp = os.path.splitext(SAIDA)[0] + ".csv"
    with open(csvp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()) if linhas else ["pacote"])
        w.writeheader()
        w.writerows(linhas)
    print(f"\n(salvo em {SAIDA} e {csvp})")
