# -*- coding: utf-8 -*-
"""Diagnóstico rápido (1–2 minutos) da saúde do celular. SOMENTE LEITURA.
Uso:  python saude_rapida.py [--saida arquivo.md]

Mostra: tempo ligado, armazenamento, RAM/troca de memória, pressão do sistema, bateria,
temperaturas e limitação de CPU, desgaste do armazenamento flash, apps fora da loja,
exceções de economia de bateria, acessibilidade/administradores e ajustes de tela.
Cada item com problema recebe uma marca [!] e entra no resumo final.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _adb  # noqa: E402

_adb.utf8_stdout()
_adb.ajuda(__doc__)
saida = None
if "--saida" in sys.argv:
    saida = sys.argv[sys.argv.index("--saida") + 1]
_adb.require_device()

linhas, alertas = [], []


def P(s=""):
    linhas.append(s)
    print(s, flush=True)


def alerta(msg):
    alertas.append(msg)
    P(f"  [!] {msg}")


def sh(cmd, t=60):
    return _adb.sh(cmd, timeout=t)


def gb(kb):
    return kb / 1048576.0


def num(s, default=None):
    try:
        return float(str(s).strip())
    except (TypeError, ValueError):
        return default


STORES = {"com.android.vending", "com.xiaomi.mipicks", "com.xiaomi.market", "com.sec.android.app.samsungapps",
          "com.huawei.appmarket", "com.amazon.venezia", "com.heytap.market", "com.oppo.market", "com.bbk.appstore",
          "com.google.android.feedback", "com.motorola.ccc.ota"}

# ---------------- identidade ----------------
marca = _adb.getprop("ro.product.brand")
modelo = _adb.getprop("ro.product.marketname") or _adb.getprop("ro.product.model")
android = _adb.getprop("ro.build.version.release")
P(f"# Diagnóstico rápido — {marca} {modelo} (Android {android})\n")
up = num(sh("cut -d' ' -f1 /proc/uptime", 20), 0) or 0
dias_ligado = up / 86400
P(f"- Ligado há {dias_ligado:.1f} dias sem reiniciar.")
if dias_ligado > 7:
    alerta(f"Aparelho ligado há {dias_ligado:.0f} dias: reiniciar libera memória e processos presos.")

# ---------------- armazenamento ----------------
P("\n## Armazenamento")
df = [l.split() for l in sh("df -k /data 2>/dev/null").splitlines() if l.strip()]
if len(df) >= 2 and len(df[-1]) >= 4:
    tot, used, avail = (num(x, 0) for x in df[-1][1:4])
    livre = 100 * avail / tot if tot else 0
    P(f"- /data: {gb(tot):.0f} GB no total, {gb(avail):.1f} GB livres ({livre:.0f} %).")
    if livre < 10:
        alerta(f"Armazenamento crítico ({livre:.0f} % livre). Abaixo de 10 % o flash fica lento e o sistema rebaixa otimizações.")
    elif livre < 20:
        alerta(f"Pouco espaço livre ({livre:.0f} %). O ideal é manter pelo menos 20 % livre.")
ds = sh("dumpsys diskstats 2>/dev/null", 60)
partes = []
for k in ["App Size", "App Data Size", "App Cache Size", "Photos Size", "Videos Size", "Audio Size",
          "Downloads Size", "System Size", "Other Size"]:
    m = re.search(rf"^{k}: (\d+)", ds, re.M)
    if m:
        partes.append(f"{k.replace(' Size', '')}: {int(m.group(1)) / 1e9:.1f} GB")
if partes:
    P("- Uso por tipo (dumpsys diskstats): " + "; ".join(partes))

# ---------------- memória ----------------
P("\n## Memória RAM e troca (swap)")
mi = dict(re.findall(r"^(\w+):\s+(\d+) kB", sh("cat /proc/meminfo", 20), re.M))
vm = dict(re.findall(r"^(\w+) (\d+)$", sh("cat /proc/vmstat", 20), re.M))
if mi:
    mt, ma = num(mi.get("MemTotal"), 0), num(mi.get("MemAvailable"), 0)
    st, sf = num(mi.get("SwapTotal"), 0), num(mi.get("SwapFree"), 0)
    P(f"- RAM: {gb(mt):.1f} GB; disponível agora {gb(ma):.2f} GB ({100 * ma / mt if mt else 0:.0f} %).")
    P(f"- Swap (zram + extensão de memória): {gb(st):.1f} GB, livre {gb(sf):.1f} GB.")
    if mt and ma / mt < 0.15:
        alerta("Pouca RAM disponível (<15 %). Muitos apps residentes em segundo plano.")
if vm:
    pout = num(vm.get("pswpout"), 0) * 4 / 1048576  # páginas de 4 KB -> GB
    oom = int(num(vm.get("oom_kill"), 0) or 0)
    stall = int(sum(num(v, 0) for k, v in vm.items() if k.startswith("allocstall")))
    por_dia = pout / max(dias_ligado, 0.1)
    P(f"- Desde o boot: {pout:.0f} GB enviados para swap ({por_dia:.0f} GB/dia), {oom} apps encerrados por falta "
      f"de memória, {stall} paradas para liberar memória.")
    if por_dia > 10 or oom > 200:
        alerta("Troca de memória intensa (thrashing): o sistema gasta CPU comprimindo e expulsando memória; "
               "causa típica de travadas.")
psi = sh('for f in memory cpu io; do echo "$f $(head -1 /proc/pressure/$f 2>/dev/null)"; done', 20)
for l in psi.splitlines():
    m = re.match(r"(\w+) some avg10=([\d.]+) avg60=([\d.]+) avg300=([\d.]+)", l)
    if m:
        P(f"- Pressão de {m.group(1)} (PSI, média de 5 min): {m.group(4)} %")
        if m.group(1) == "memory" and float(m.group(4)) > 10:
            alerta(f"Pressão de memória alta ({m.group(4)} % do tempo com tarefas esperando memória).")
        if m.group(1) == "io" and float(m.group(4)) > 10:
            alerta(f"Pressão de E/S alta ({m.group(4)} %): armazenamento lento ou cheio.")

# ---------------- bateria ----------------
P("\n## Bateria")
b = dict(re.findall(r"^\s+([\w ]+): (.+)$", sh("dumpsys battery", 20), re.M))
saude = {"1": "desconhecida", "2": "boa", "3": "superaquecida", "4": "morta", "5": "sobretensão", "6": "falha", "7": "fria"}
estado = {"1": "?", "2": "carregando", "3": "descarregando", "4": "não carregando", "5": "cheia"}
if b:
    temp = (num(b.get("temperature"), 0) or 0) / 10
    P(f"- Nível {b.get('level', '?')} %, {estado.get(b.get('status', ''), '?')}, temperatura {temp:.1f} °C, "
      f"tensão {b.get('voltage', '?')} mV, saúde informada: {saude.get(b.get('health', ''), b.get('health', '?'))}.")
    if temp >= 40:
        alerta(f"Bateria quente agora ({temp:.0f} °C). Acima de ~40 °C o sistema corta desempenho, brilho e carga.")
    elif temp >= 37:
        alerta(f"Bateria morna ({temp:.0f} °C): vários aparelhos já começam a limitar desempenho e carga nessa faixa.")
bs = sh("dumpsys batterystats 2>/dev/null | grep -E 'Estimated battery capacity|learned battery capacity'", 180)
est = re.search(r"Estimated battery capacity: (\d+)", bs)
lrn = re.search(r"Last learned battery capacity: (\d+)", bs)
design = None
for p in ["/sys/class/power_supply/battery/charge_full_design", "/sys/class/power_supply/bms/charge_full_design"]:
    v = num(sh(f"cat {p} 2>/dev/null", 10))
    if v:
        design = v / 1000 if v > 100000 else v
        break
ciclos = None
for p in ["/sys/class/power_supply/battery/cycle_count", "/sys/class/power_supply/bms/cycle_count"]:
    v = num(sh(f"cat {p} 2>/dev/null", 10))
    if v is not None:
        ciclos = int(v)
        break
if est or lrn:
    e = int(est.group(1)) if est and int(est.group(1)) > 0 else None
    l_ = int(lrn.group(1)) if lrn and int(lrn.group(1)) > 0 else None
    txt = f"- Capacidade estimada pelo Android: {e or '?'} mAh; última capacidade aprendida: {l_ or '?'} mAh"
    if design and (e or l_):
        pct = 100 * (e or l_) / design
        txt += f"; de fábrica: {design:.0f} mAh, ou seja, cerca de {pct:.0f} % da original"
        P(txt + ".")
        if pct < 80:
            alerta(f"Bateria desgastada (~{pct:.0f} % da capacidade original). Abaixo de 80 % a troca é recomendada.")
    else:
        P(txt + ". A capacidade de fábrica não é legível sem root: compare com a ficha técnica do modelo.")
else:
    P("- Estimativa de capacidade indisponível neste aparelho (costuma aparecer após alguns ciclos completos de carga).")
if ciclos is not None:
    P(f"- Ciclos de carga: {ciclos}")

# ---------------- térmica e CPU ----------------
P("\n## Temperatura e limitação de desempenho")
ts = re.search(r"Thermal Status: (\d)", sh("dumpsys thermalservice 2>/dev/null", 30))
if ts:
    nomes = ["nenhuma", "leve", "moderada", "severa", "crítica", "emergência", "desligamento"]
    P(f"- Status térmico do Android: {ts.group(1)} ({nomes[int(ts.group(1))]}). Vários fabricantes limitam por um "
      f"serviço próprio sem refletir aqui (ex.: Xiaomi mi_thermald).")
zonas = []
for l in sh('for z in /sys/class/thermal/thermal_zone*; do echo "$(cat $z/type 2>/dev/null)|$(cat $z/temp 2>/dev/null)"; done', 60).splitlines():
    if "|" in l:
        t, v = l.split("|", 1)
        v = num(v)
        if v is None:
            continue
        c = v / 1000 if abs(v) > 1000 else v
        if 0 < c < 130:
            zonas.append((c, t))
zonas.sort(reverse=True)
if zonas:
    P("- Sensores mais quentes agora: " + ", ".join(f"{t} {c:.0f} °C" for c, t in zonas[:6]))
tm = sh('cd /sys/class/thermal/thermal_message 2>/dev/null && for f in sconfig temp_state board_sensor_temp; do echo "$f=$(cat $f 2>/dev/null)"; done', 20).strip()
if tm:
    P(f"- Xiaomi thermal_message: {', '.join(tm.splitlines())} (sconfig = cenário térmico ativo; board_sensor_temp em m°C)")
cpus = sh('for p in /sys/devices/system/cpu/cpufreq/policy*; do echo "$(basename $p)|$(cat $p/related_cpus)|$(cat $p/cpuinfo_max_freq)|$(cat $p/scaling_max_freq)|$(cat $p/scaling_cur_freq)"; done 2>/dev/null', 30)
for l in cpus.splitlines():
    f = l.split("|")
    if len(f) == 5 and f[2].strip().isdigit() and f[3].strip().isdigit():
        mx, lim = int(f[2]) / 1e6, int(f[3]) / 1e6
        cur = (num(f[4], 0) or 0) / 1e6
        P(f"- CPU {f[1].strip()}: máximo de fábrica {mx:.2f} GHz, teto atual {lim:.2f} GHz, agora {cur:.2f} GHz")
        if lim < mx * 0.97:
            alerta(f"Núcleos {f[1].strip()} limitados agora a {lim:.2f} de {mx:.2f} GHz (térmica ou modo de economia).")
gpu = sh('cd /sys/class/kgsl/kgsl-3d0 2>/dev/null && echo "$(cat max_gpuclk 2>/dev/null)|$(cat devfreq/max_freq 2>/dev/null)|$(cat gpuclk 2>/dev/null)"', 20).strip()
if gpu.count("|") == 2 and gpu.split("|")[0].isdigit():
    a, bmax, c = ((num(x, 0) or 0) / 1e6 for x in gpu.split("|"))
    P(f"- GPU Adreno: máximo {a:.0f} MHz, teto atual {bmax:.0f} MHz, agora {c:.0f} MHz")
    if bmax and a and bmax < a * 0.97:
        alerta(f"GPU limitada agora a {bmax:.0f} de {a:.0f} MHz.")

# ---------------- desgaste do armazenamento ----------------
P("\n## Desgaste do armazenamento flash")
vida = {0: "não informado", 1: "0–10 %", 2: "10–20 %", 3: "20–30 %", 4: "30–40 %", 5: "40–50 %", 6: "50–60 %",
        7: "60–70 %", 8: "70–80 %", 9: "80–90 %", 10: "90–100 %", 11: "vida útil excedida"}
w = sh('for f in /sys/devices/virtual/mi_memory/mi_memory_device/ufshcd0/dump_health_desc '
       '/sys/devices/platform/soc/*ufshc*/health_descriptor/life_time_estimation_a '
       '/sys/devices/platform/soc/*ufshc*/health_descriptor/life_time_estimation_b '
       '/sys/class/mmc_host/mmc0/mmc0:*/life_time; '
       'do [ -r "$f" ] && echo "== $f" && cat "$f" 2>/dev/null; done', 30)
achou = False
for k, rx in [("A", r"(?:LifeTimeEstA\s*=\s*|life_time_estimation_a\n)(0x[0-9a-fA-F]+|\d+)"),
              ("B", r"(?:LifeTimeEstB\s*=\s*|life_time_estimation_b\n)(0x[0-9a-fA-F]+|\d+)")]:
    m = re.search(rx, w)
    if m:
        v = int(m.group(1), 16) if m.group(1).startswith("0x") else int(m.group(1))
        achou = True
        P(f"- Vida consumida (estimativa tipo {k}): {vida.get(v, hex(v))}")
        if v >= 8:
            alerta(f"Armazenamento flash com desgaste alto (tipo {k}: {vida.get(v)}).")
mm = re.search(r"life_time\n(0x[0-9a-fA-F]+) (0x[0-9a-fA-F]+)", w)
if mm and not achou:
    achou = True
    for k, v in zip("AB", mm.groups()):
        P(f"- eMMC, vida consumida (tipo {k}): {vida.get(int(v, 16), v)}")
if not achou:
    P("- Não legível pelo ADB neste aparelho. A varredura completa (coletar.py, com bugreport) costuma trazer esse dado.")

# ---------------- apps ----------------
P("\n## Apps")
todos = sh("pm list packages 2>/dev/null | wc -l", 30).strip()
terc = [l for l in sh("pm list packages -3 -i 2>/dev/null", 60).splitlines() if l.startswith("package:")]
desat = sh("pm list packages -d 2>/dev/null | wc -l", 30).strip()
fora = []
for l in terc:
    m = re.match(r"package:(\S+)\s+installer=(\S+)", l)
    if m and m.group(2) not in STORES:
        fora.append(f"{m.group(1)} (instalador: {m.group(2)})")
P(f"- Pacotes: {todos} no total, {len(terc)} instalados pelo usuário, {desat} desativados.")
if fora:
    P(f"- Instalados fora de lojas oficiais ({len(fora)}): " + "; ".join(fora[:25]) + (" ..." if len(fora) > 25 else ""))
    alerta(f"{len(fora)} apps vieram de fora das lojas oficiais: analisar com analisar_apks.py "
           f"(risco de minerador ou espionagem).")
wl = [l.split(",")[1] for l in sh("dumpsys deviceidle whitelist 2>/dev/null", 30).splitlines()
      if l.startswith("user,") and l.count(",") >= 1]
if wl:
    P(f"- Apps isentos da economia de bateria (Doze) por escolha do usuário ou do fabricante: {', '.join(wl)}")
acc = sh("settings get secure enabled_accessibility_services", 20).strip()
if acc and acc != "null":
    P(f"- Serviços de acessibilidade ativos (podem ler a tela): {acc}")
    alerta("Há serviços de acessibilidade ativos: confirme que todos são conhecidos e desejados.")
dp = sh("dumpsys device_policy 2>/dev/null | grep -A8 'Enabled Device Admins'", 30)
adm = sorted({l.strip().rstrip(':').split('/')[0] for l in dp.splitlines()
              if re.match(r"^\s+[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+:?\s*$", l)})
if adm:
    P(f"- Apps com permissão de administrador do dispositivo: {', '.join(adm)}")

# ---------------- tela e animações ----------------
P("\n## Tela e animações")
an = [sh(f"settings get global {k}", 20).strip() for k in
      ("window_animation_scale", "transition_animation_scale", "animator_duration_scale")]
P(f"- Escalas de animação (janela/transição/duração): {' / '.join(a if a and a != 'null' else '1.0' for a in an)} "
  f"(0.5 deixa a navegação mais ágil)")
rr = sh("dumpsys display 2>/dev/null | grep -m3 -E 'renderFrameRate|mActiveSfDisplayMode'", 30)
m = re.search(r"(?:renderFrameRate|fps)=([\d.]+)", rr)
if m:
    P(f"- Taxa de atualização em uso agora: {float(m.group(1)):.0f} Hz")
pk = [x for x in sh("settings get system peak_refresh_rate; settings get system min_refresh_rate", 20).split()]
if pk and any(x != "null" for x in pk):
    P(f"- Ajustes de taxa (peak/min): {' / '.join(pk)}")

# ---------------- consumo agora ----------------
P("\n## Quem está consumindo agora")
mem = sh("dumpsys meminfo 2>/dev/null", 120)
m = re.search(r"Total (?:PSS|RSS) by process:\n((?:.*\n){1,12})", mem)
if m:
    tops = []
    for l in m.group(1).splitlines()[:10]:
        mm = re.match(r"\s*([\d,]+)K: (\S+)", l)
        if mm:
            tops.append(f"{mm.group(2)} {int(mm.group(1).replace(',', '')) / 1024:.0f} MB")
    if tops:
        P("- Maiores consumidores de RAM: " + ", ".join(tops))
top = sh("top -b -n 1 -m 8 -o %CPU,RES,NAME 2>/dev/null | tail -n 9", 30)
if top.strip():
    P("- Maiores consumidores de CPU (instantâneo):")
    for l in top.splitlines():
        if l.strip():
            P("    " + l.strip())

# ---------------- resumo ----------------
P("\n## Resumo")
if alertas:
    P(f"{len(alertas)} pontos de atenção:")
    for i, a in enumerate(alertas, 1):
        P(f"{i}. {a}")
else:
    P("Nenhum problema evidente no diagnóstico rápido.")
if saida:
    os.makedirs(os.path.dirname(os.path.abspath(saida)), exist_ok=True)
    with open(saida, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    print(f"\n(salvo em {saida})")
