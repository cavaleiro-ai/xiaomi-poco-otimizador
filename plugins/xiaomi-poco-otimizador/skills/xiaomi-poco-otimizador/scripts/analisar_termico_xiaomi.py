# -*- coding: utf-8 -*-
"""Decodifica o log interno do daemon térmico da Xiaomi/POCO/Redmi (mi_thermald), que vem no bugreport
(seções 'THERMAL DUMP LOG' e 'LAST THERMAL DUMP LOG' do arquivo dumpstate_board.txt).

Cada linha do log é uma decisão aplicada: "em tal instante, com o sensor X em Y, o limite do dispositivo Z
passou a ser W". A partir disso o script reconstrói a política real do aparelho:
  - em que temperatura cada teto de CPU/GPU é aplicado e quanto tempo o aparelho passou limitado;
  - teto de brilho e nível de corte de corrente de carga por temperatura;
  - cenários (normal, câmera, vídeo, jogo...) e eventos do BCL (limitador por bateria fraca);
  - opcionalmente (precisa de numpy), a fórmula do "sensor virtual" que comanda os cortes.

Uso:
  python analisar_termico_xiaomi.py <bugreport.zip | pasta extraída | dumpstate_board.txt> [saida.md]
"""
import collections
import datetime
import io
import os
import re
import statistics
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _adb  # noqa: E402

_adb.utf8_stdout()
_adb.ajuda(__doc__)
if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)
src = sys.argv[1]
out_path = sys.argv[2] if len(sys.argv) > 2 else None


def ler_fonte(p):
    """Devolve (texto, nome_de_referência_para_achar_o_ano)."""
    if os.path.isdir(p):
        for dp, _, fs in os.walk(p):
            for f in fs:
                if f == "dumpstate_board.txt":
                    nomes = " ".join(fs + os.listdir(os.path.dirname(dp)) if os.path.dirname(dp) else fs)
                    with open(os.path.join(dp, f), encoding="utf-8", errors="replace") as fh:
                        return fh.read(), nomes + " " + p
        for dp, _, fs in os.walk(p):
            for f in fs:
                if f.endswith(".zip"):
                    return ler_fonte(os.path.join(dp, f))
        sys.exit("dumpstate_board.txt não encontrado na pasta.")
    if p.lower().endswith(".zip"):
        with zipfile.ZipFile(p) as zf:
            nomes = [n for n in zf.namelist() if n.endswith("dumpstate_board.txt")]
            if not nomes:
                sys.exit("dumpstate_board.txt não está neste zip (o aparelho pode não ser Xiaomi ou o bugreport veio incompleto).")
            return zf.read(nomes[0]).decode("utf-8", "replace"), os.path.basename(p)
    with open(p, encoding="utf-8", errors="replace") as fh:
        return fh.read(), os.path.basename(p) + " " + os.path.abspath(p)


texto, ref = ler_fonte(src)
m = re.search(r"(20\d\d)-(\d\d)-(\d\d)-\d\d-\d\d-\d\d", ref)
ano_ref, mes_ref = (int(m.group(1)), int(m.group(2))) if m else (datetime.date.today().year, datetime.date.today().month)

RX = re.compile(r"^(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)\[([A-Za-z0-9_-]+)\]\[([A-Za-z0-9_-]+) (-?\d+)\] \{(.*)$")
FX = re.compile(r"\[([A-Za-z0-9_.-]+) (-?\d+)\]")

secoes = collections.OrderedDict()
atual = None
tem_marcador = "THERMAL DUMP LOG" in texto
for ln in texto.splitlines():
    if ln.startswith("------ "):
        if "THERMAL DUMP LOG" in ln:
            atual = "boot anterior (LAST THERMAL DUMP LOG)" if "LAST" in ln else "boot atual (THERMAL DUMP LOG)"
            secoes.setdefault(atual, [])
        elif "was the duration" not in ln:
            atual = None
        continue
    if not tem_marcador:
        atual = "log completo"
        secoes.setdefault(atual, [])
    if atual is None:
        continue
    mm = RX.match(ln)
    if not mm:
        continue
    mo, d, h, mi, s, algo, sensor, sval, rest = mm.groups()
    ano = ano_ref - 1 if int(mo) > mes_ref else ano_ref
    try:
        t = datetime.datetime(ano, int(mo), int(d), int(h), int(mi), int(s))
    except ValueError:
        continue
    f = FX.findall(rest)
    if not f:
        continue
    partes = algo.split("-")
    cen = "NORMAL" if partes[0] in ("SS", "MONITOR") else partes[0]
    campos = {}
    for k, v in f[1:]:
        campos[k] = int(v)
    secoes[atual].append(dict(t=t, algo=algo, cen=cen, sensor=sensor, sval=int(sval), dev=f[0][0], alvo=int(f[0][1]),
                              campos=campos))

md = []


def P(s=""):
    md.append(s)
    print(s)


total = sum(len(v) for v in secoes.values())
if not total:
    sys.exit("Nenhuma linha do log térmico da Xiaomi encontrada. Em aparelhos de outras marcas este log não existe; "
             "use os dados de 04_sysfs/thermal_zones_cooling.txt e 08_processos/cpufreq_snapshot.txt.")

P("# Análise do log térmico interno (mi_thermald)\n")
P(f"Fonte: `{os.path.basename(src)}`. Cada linha do log é uma decisão aplicada pelo daemon térmico do fabricante. "
  f"Total de decisões: {total}.\n")
P("Como ler: 'sensor de disparo' é o sensor que o daemon usou na decisão (normalmente o VIRTUAL-SENSOR, uma média "
  "ponderada de vários termistores, em m°C). As tabelas mostram, para cada limite aplicado, em que temperatura ele "
  "foi decidido. Tempo ponderado = quanto tempo cada limite ficou valendo até a decisão seguinte (lacunas acima de "
  "6 h são truncadas porque o log é rotativo).\n")


def fmt_val(dev, v):
    if (dev.startswith("cpu") or dev.startswith("gpu")) and v > 10000:
        return f"{v / 1e6:.2f} GHz" if v > 100000 else f"{v / 1e3:.0f} MHz"
    return str(v)


def temp_c(sensor, v):
    return v / 1000 if (sensor == "VIRTUAL-SENSOR" or "therm" in sensor.lower() or "temp" in sensor.lower()) and abs(v) > 200 else v


resumo = []
for nome_sec, ev in secoes.items():
    if not ev:
        continue
    ev.sort(key=lambda e: e["t"])
    horas = (ev[-1]["t"] - ev[0]["t"]).total_seconds() / 3600
    P(f"\n## Período: {nome_sec}")
    P(f"- {len(ev)} decisões de {ev[0]['t']:%d/%m/%Y %H:%M} a {ev[-1]['t']:%d/%m/%Y %H:%M} ({horas:.0f} h)")
    dur = collections.Counter()
    for i, e in enumerate(ev[:-1]):
        dur[e["cen"]] += min((ev[i + 1]["t"] - e["t"]).total_seconds(), 6 * 3600)
    tot = sum(dur.values()) or 1
    P("- Tempo por cenário: " + ", ".join(f"{c} {100 * v / tot:.0f} %" for c, v in dur.most_common()))

    por_dev = collections.defaultdict(list)
    for e in ev:
        por_dev[e["dev"]].append(e)
    devs = sorted(por_dev, key=lambda d: -len(por_dev[d]))
    P(f"- Dispositivos controlados: " + ", ".join(f"`{d}` ({len(por_dev[d])})" for d in devs))

    for dev in devs:
        es = por_dev[dev]
        if len(es) < 20:
            continue
        sensor = collections.Counter(e["sensor"] for e in es).most_common(1)[0][0]
        dt = collections.Counter()
        for i, e in enumerate(es):
            fim = es[i + 1]["t"] if i + 1 < len(es) else ev[-1]["t"]
            dt[e["alvo"]] += min((fim - e["t"]).total_seconds(), 6 * 3600)
        totd = sum(dt.values()) or 1
        vmax = max(dt)
        P(f"\n### `{dev}` — {len(es)} decisões, sensor de disparo: {sensor}")
        P("| limite aplicado | tempo valendo | % do tempo | n | temp. de disparo p10 / mediana / p90 |")
        P("|---:|---:|---:|---:|---|")
        by = collections.defaultdict(list)
        for e in es:
            by[e["alvo"]].append(temp_c(e["sensor"], e["sval"]))
        for v in sorted(dt, key=lambda x: -x):
            xs = sorted(by.get(v, [0]))
            n = len(xs)
            P(f"| {fmt_val(dev, v)} | {dt[v] / 3600:.1f} h | {100 * dt[v] / totd:.0f} % | {n} | "
              f"{xs[int(0.1 * (n - 1))]:.1f} / {statistics.median(xs):.1f} / {xs[int(0.9 * (n - 1))]:.1f} |")
        if (dev.startswith("cpu") or dev.startswith("gpu")) and vmax > 10000:
            # valor = frequência máxima permitida: limitado quando abaixo do maior valor observado
            lim = sum(s for v, s in dt.items() if v < vmax)
            P(f"\nTempo com `{dev}` abaixo do máximo observado ({fmt_val(dev, vmax)}): **{100 * lim / totd:.0f} %**.")
            resumo.append(f"{nome_sec}: `{dev}` limitado abaixo de {fmt_val(dev, vmax)} em {100 * lim / totd:.0f} % do tempo")
        elif 0 in dt and (dev.startswith("gpu") or "backlight" in dev or dev.startswith("hotplug")):
            # valor = nível/estado de limitação: 0 = sem limite
            lim = sum(s for v, s in dt.items() if v != 0)
            P(f"\nTempo com limitação ativa em `{dev}` (valor diferente de 0): **{100 * lim / totd:.0f} %**.")
            resumo.append(f"{nome_sec}: limitação ativa em `{dev}` em {100 * lim / totd:.0f} % do tempo")
        if "backlight" in dev:
            P("\nObs.: em vários modelos Xiaomi o valor do limitador de brilho é subtraído do brilho máximo "
              "(teto = máximo − valor). Confira a semântica no log do SDM/SurfaceFlinger (`HWBacklightThermal`) do bugreport.")

    bat = [e for e in por_dev.get("battery", []) if e["campos"].get("current", 0) > 0]
    if bat:
        byl = collections.defaultdict(list)
        for e in bat:
            byl[e["alvo"]].append(e["campos"]["current"] / 1000)
        P("\n### Corrente observada por nível térmico de carga (`battery`; valores positivos = carregando)")
        P("| nível | n | corrente mediana (mA) | máxima (mA) |")
        P("|---:|---:|---:|---:|")
        for v in sorted(byl, reverse=True):
            xs = sorted(byl[v])
            P(f"| {v} | {len(xs)} | {statistics.median(xs):.0f} | {xs[-1]:.0f} |")

    bcl = [e for e in ev if e["algo"].endswith("BCL")]
    if bcl:
        hp = [e for e in bcl if any(v for k, v in e["campos"].items() if k.startswith("hotplug"))]
        P(f"\n### BCL (limitador por bateria fraca/corrente alta): {len(bcl)} eventos; com núcleos desligados (hotplug): {len(hp)}")

    cpu_devs = [d for d in devs if d.startswith("cpu") and len(por_dev[d]) >= 20]
    if cpu_devs:
        dev = max(cpu_devs, key=lambda d: max(e["alvo"] for e in por_dev[d]))
        es = por_dev[dev]
        vmax = max(e["alvo"] for e in es)
        hod, hall = collections.Counter(), collections.Counter()
        for i, e in enumerate(es):
            fim = es[i + 1]["t"] if i + 1 < len(es) else ev[-1]["t"]
            s_ = min((fim - e["t"]).total_seconds(), 6 * 3600)
            hall[e["t"].hour] += s_
            if e["alvo"] < vmax:
                hod[e["t"].hour] += s_
        P(f"\n### `{dev}` limitado, por hora do dia")
        P(" ".join(f"{h:02d}h:{(100 * hod[h] / hall[h] if hall[h] else 0):.0f}%" for h in range(24)))

    sens = collections.defaultdict(list)
    for e in ev:
        for k, v in e["campos"].items():
            if ("therm" in k or k in ("battery",)) and v > 0:
                sens[k].append(v / 1000 if v > 1000 else v)
    if sens:
        P("\n### Faixa dos termistores registrados (°C: mínimo / mediana / máximo)")
        for k, xs in sorted(sens.items()):
            xs.sort()
            P(f"- {k}: {xs[0]:.0f} / {statistics.median(xs):.0f} / {xs[-1]:.0f}")

# ---------- fórmula do sensor virtual (opcional) ----------
try:
    import numpy as np
except ImportError:
    np = None
todos = [e for v in secoes.values() for e in v if e["sensor"] == "VIRTUAL-SENSOR"]
if np is not None and len(todos) > 300:
    chaves = collections.Counter(k for e in todos for k in e["campos"])
    cand = []
    for k, n in chaves.items():
        if n < 0.9 * len(todos):
            continue
        vals = [e["campos"][k] for e in todos if k in e["campos"]]
        med = statistics.median(vals)
        if 15000 < med < 90000 and ("therm" in k or k == "battery"):
            cand.append(k)
    linhas = [e for e in todos if all(e["campos"].get(k, 0) > 0 for k in cand)]
    if cand and len(linhas) > 200:
        X = np.array([[e["campos"][k] for k in cand] + [1.0] for e in linhas], float)
        y = np.array([e["sval"] for e in linhas], float)
        w, *_ = np.linalg.lstsq(X, y, rcond=None)
        pred = X @ w
        r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
        P("\n## Fórmula reconstruída do VIRTUAL-SENSOR (regressão linear)")
        P(f"{len(linhas)} amostras, R² = {r2:.4f}, erro médio {abs(y - pred).mean() / 1000:.2f} °C. "
          f"Pesos em milésimos (formato dos arquivos .conf da Xiaomi); a soma perto de 1000 indica média ponderada.")
        for k, v in sorted(zip(cand, w[:-1]), key=lambda kv: -abs(kv[1])):
            P(f"- {k}: {v * 1000:.0f}")
        P(f"- compensação: {w[-1] / 1000:+.1f} °C")
        P("Interpretação: os sensores com maior peso são os que mais disparam os cortes. Pesos negativos grandes "
          "costumam indicar sensores muito correlacionados; leia o conjunto, não um peso isolado.")

if resumo:
    P("\n## Resumo")
    for r in resumo:
        P(f"- {r}")

if out_path:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\n(salvo em {out_path})")
