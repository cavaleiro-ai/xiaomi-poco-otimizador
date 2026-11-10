# -*- coding: utf-8 -*-
"""Análise estática de APKs: procura mineradores de criptomoeda, permissões de risco, assinatura de
depuração, código que mexe em limites de CPU/bateria/tela e os servidores contatados.
Não executa nada: só lê os bytes dos arquivos. SOMENTE LEITURA no aparelho (só copia os APKs).

Uso:
  python analisar_apks.py --pasta PASTA_COM_APKS [--saida relatorio.md]
  python analisar_apks.py --puxar PASTA_DESTINO [pacote ...] [--todos-terceiros] [--saida relatorio.md]

  --puxar sem pacotes  copia só os apps instalados FORA de lojas oficiais (onde aparecem mineradores e espiões)
  --todos-terceiros    copia todos os apps instalados pelo usuário (pode passar de 10 GB)

Leitura do veredito:
  ALTO   = termos inequívocos de mineração (stratum, xmrig, MiningService...) — tratar como minerador
  MÉDIO  = vários termos ligados a mineração ou a permissões de controle total — revisar com o dono
  baixo  = nada relevante encontrado (não garante que o app é seguro)
"""
import collections
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _adb  # noqa: E402

_adb.utf8_stdout()
_adb.ajuda(__doc__)


def arg(nome, padrao=None):
    return sys.argv[sys.argv.index(nome) + 1] if nome in sys.argv else padrao


SAIDA = arg("--saida")
STORES = {"com.android.vending", "com.xiaomi.mipicks", "com.xiaomi.market", "com.sec.android.app.samsungapps",
          "com.huawei.appmarket", "com.amazon.venezia", "com.heytap.market", "com.oppo.market", "com.bbk.appstore"}

if "--puxar" in sys.argv:
    dest = _adb.caminho_local(arg("--puxar"))
    i = sys.argv.index("--puxar")
    extras = [a for a in sys.argv[i + 2:] if not a.startswith("--") and a != SAIDA]
    _adb.require_device()
    if extras:
        alvo = extras
    else:
        txt = _adb.sh("pm list packages -3 -i", timeout=60)
        alvo = []
        for ln in txt.splitlines():
            m = re.match(r"package:(\S+)(?:\s+installer=(\S+))?", ln)
            if m and ("--todos-terceiros" in sys.argv or (m.group(2) or "null") not in STORES):
                alvo.append(m.group(1))
    if not alvo:
        print("Nenhum app instalado fora de lojas oficiais. Nada a analisar (bom sinal). "
              "Para analisar outros, passe os pacotes ou use --todos-terceiros.")
        sys.exit(0)
    print(f"Copiando {len(alvo)} app(s) para {dest} ...", flush=True)
    for p in alvo:
        caminhos = [l.replace("package:", "").strip() for l in _adb.sh(f"pm path {p}", timeout=30).splitlines() if l.startswith("package:")]
        if not caminhos:
            print(f"  (não encontrado) {p}")
            continue
        os.makedirs(os.path.join(dest, p), exist_ok=True)
        for c in caminhos:
            _adb.adb("pull", c, os.path.join(dest, p, os.path.basename(c)), timeout=1800)
        print(f"  {p}: {len(caminhos)} arquivo(s)")
    pasta = dest
else:
    pasta = arg("--pasta")
    if not pasta:
        print(__doc__)
        sys.exit(1)

# (rótulo, expressão) — termos inequívocos de mineração
ALTO = [("stratum://", rb"stratum\+(?:tcp|ssl|tls)://"), ("xmrig", rb"xmrig"), ("cryptonight", rb"cryptonight"),
        ("randomx", rb"randomx"), ("coinhive", rb"coin-?hive"), ("minergate", rb"minergate"), ("nicehash", rb"nicehash"),
        ("moneroocean", rb"moneroocean"), ("supportxmr", rb"supportxmr"), ("nanopool", rb"nanopool"),
        ("hashvault", rb"hashvault"), ("unmineable", rb"unmineable"), ("herominers", rb"herominers"),
        ("donate-level", rb"donate-level"), ("cpuminer", rb"cpuminer"), ("minerd", rb"\bminerd\b"),
        ("MiningService", rb"MiningService"), ("startMining", rb"[Ss]tart_?[Mm]ining"), ("mining_service", rb"mining_service"),
        ("MiningNative", rb"MiningNative")]
# termos que aparecem em mineradores, mas também em apps legítimos de cripto
# (aplicados sobre o conteúdo convertido para minúsculas; por isso os padrões são minúsculos)
MEDIO = [("mining", rb"\bmining\b"), ("mineração", rb"minera(?:\xc3\xa7|c)(?:\xc3\xa3|a)o"),
         ("minerar", rb"\bminerar\b"), ("hashrate", rb"hash_?rate"), ("miner", rb"\bminer\b")]
# código que lê ou mexe em limites de hardware, bateria, tela ou detecta benchmarks
LIMITES = [("cycle_count", rb"cycle_count"), ("battery_age", rb"batt(?:ery)?_age"), ("aging", rb"\baging\b"),
           ("degrad", rb"degrad"), ("soh", rb"\bsoh\b"), ("scaling_max_freq", rb"scaling_max_freq"),
           ("cpuinfo_max_freq", rb"cpuinfo_max_freq"), ("thermal_message", rb"thermal_message"), ("temp_state", rb"temp_state"),
           ("sconfig", rb"\bsconfig\b"), ("cpu_limits", rb"cpu_limits"), ("throttl", rb"throttl"),
           ("dynamic_fps", rb"dynamic_fps"), ("max_brightness", rb"max_brightness"),
           ("constant_charge_current", rb"constant_charge_current"), ("input_suspend", rb"input_suspend"),
           ("charge_control_limit", rb"charge_control_limit"), ("benchmark", rb"benchmark"),
           ("antutu", rb"com\.antutu"), ("geekbench", rb"primatelabs")]


def compilar(lista):
    """Uma única passada por arquivo: expressão combinada + identificação do rótulo só nos acertos."""
    combinada = re.compile(b"|".join(b"(?:" + p + b")" for _, p in lista))
    individuais = [(rot, re.compile(p)) for rot, p in lista]
    return combinada, individuais


def contar(cat, dados, contador):
    combinada, individuais = cat
    for m in combinada.finditer(dados):
        s = m.group(0)
        for rot, rx in individuais:
            if rx.fullmatch(s) or rx.search(s):
                contador[rot] += 1
                break


CAT_ALTO, CAT_MEDIO, CAT_LIM = compilar(ALTO), compilar(MEDIO), compilar(LIMITES)
# certificado X.509 de depuração do Android: CN "Android Debug" codificado em DER (PrintableString ou UTF8String)
DEBUG_CERT = (b"\x13\x0dAndroid Debug", b"\x0c\x0dAndroid Debug")
PERMS = ["BIND_ACCESSIBILITY_SERVICE", "BIND_DEVICE_ADMIN", "REQUEST_INSTALL_PACKAGES", "REQUEST_DELETE_PACKAGES",
         "SYSTEM_ALERT_WINDOW", "RECEIVE_BOOT_COMPLETED", "FOREGROUND_SERVICE_SPECIAL_USE", "QUERY_ALL_PACKAGES",
         "READ_SMS", "RECEIVE_SMS", "READ_CALL_LOG", "ACCESS_BACKGROUND_LOCATION", "RECORD_AUDIO", "READ_CONTACTS",
         "WRITE_SECURE_SETTINGS", "PACKAGE_USAGE_STATS", "BIND_NOTIFICATION_LISTENER_SERVICE",
         "MANAGE_EXTERNAL_STORAGE", "android.uid.system"]
PERMS_GRAVES = {"BIND_ACCESSIBILITY_SERVICE", "BIND_DEVICE_ADMIN", "READ_SMS", "RECEIVE_SMS",
                "BIND_NOTIFICATION_LISTENER_SERVICE", "REQUEST_INSTALL_PACKAGES"}
URL = re.compile(rb"(?:https?|wss?|stratum\+tcp|stratum\+ssl)://([A-Za-z0-9.-]{4,80})")
LER = re.compile(r"(\.dex|\.so|\.json|\.js|\.txt|\.properties|\.xml|\.conf|\.cfg|\.dat|\.bin)$|^assets/|^res/raw/", re.I)
COMUNS = re.compile(r"(google|gstatic|android\.com|schemas\.|w3\.org|apache\.org|xmlpull|ns\.adobe|example\.|localhost|"
                    r"facebook\.com/tr|crashlytics|firebase|youtube\.com|play\.google)", re.I)


def analisar(arquivos, nome):
    r = dict(nome=nome, mb=sum(os.path.getsize(a) for a in arquivos) / 1e6, debug=False, alto=collections.Counter(),
             medio=collections.Counter(), limites=collections.Counter(), perms=set(), hosts=collections.Counter(),
             libs=set(), erro="")
    for a in arquivos:
        try:
            with open(a, "rb") as fh:
                bruto = fh.read()
        except OSError as e:
            r["erro"] = str(e)
            continue
        if any(sig in bruto for sig in DEBUG_CERT):
            r["debug"] = True
        del bruto
        try:
            zf = zipfile.ZipFile(a)
        except zipfile.BadZipFile:
            r["erro"] = "arquivo não é um APK/JAR válido"
            continue
        with zf:
            for info in zf.infolist():
                n = info.filename
                if n.startswith("lib/") and n.endswith(".so"):
                    r["libs"].add(os.path.basename(n))
                if not (LER.search(n) or n == "AndroidManifest.xml") or info.file_size > 300 * 1024 * 1024:
                    continue
                try:
                    dados = zf.read(info)
                except Exception:
                    continue
                contar(CAT_ALTO, dados, r["alto"])
                baixo = dados.lower()   # MEDIO e LIMITES usam padrões minúsculos (mais rápido que (?i))
                contar(CAT_MEDIO, baixo, r["medio"])
                contar(CAT_LIM, baixo, r["limites"])
                del baixo
                if n == "AndroidManifest.xml":
                    for p in PERMS:
                        if p.encode() in dados or p.encode("utf-16-le") in dados:
                            r["perms"].add(p)
                if n.endswith((".dex", ".so", ".json", ".js")) or n.startswith("assets/"):
                    for h in URL.findall(dados):
                        h = h.decode("latin-1").strip(".").lower()
                        if "." in h and not COMUNS.search(h):
                            r["hosts"][h] += 1
    graves = r["perms"] & PERMS_GRAVES
    if r["alto"]:
        r["veredito"] = "ALTO"
    elif len(r["medio"]) >= 2 or (r["medio"] and r["debug"]) or len(graves) >= 2:
        r["veredito"] = "MÉDIO"
    else:
        r["veredito"] = "baixo"
    return r


# agrupa: subpasta = um app (APKs divididos); arquivo solto = um app
grupos = collections.OrderedDict()
for dp, ds, fs in os.walk(pasta):
    for f in sorted(fs):
        if f.lower().endswith((".apk", ".jar", ".apks")):
            rel = os.path.relpath(dp, pasta)
            if rel != ".":
                chave = rel.split(os.sep)[0]          # PASTA/<pacote>/base.apk, split_*.apk
            elif "__" in f:
                chave = f.split("__")[0]              # <pacote>__base.apk
            else:
                chave = os.path.splitext(f)[0]
            grupos.setdefault(chave, []).append(os.path.join(dp, f))
if not grupos:
    sys.exit(f"Nenhum .apk/.jar em {pasta}")

res = []
for i, (nome, arqs) in enumerate(grupos.items(), 1):
    print(f"[{i}/{len(grupos)}] {nome}", flush=True)
    res.append(analisar(arqs, nome))
ordem = {"ALTO": 0, "MÉDIO": 1, "baixo": 2}
res.sort(key=lambda r: (ordem[r["veredito"]], r["nome"]))

md = ["# Análise estática de APKs", "",
      f"Pasta analisada: `{pasta}` — {len(res)} app(s). Método: leitura dos bytes de dex/so/assets/manifesto; "
      f"nada foi executado. Um veredito 'baixo' não prova que o app é seguro.", "",
      "| app | veredito | assinatura de depuração | indícios de mineração | permissões sensíveis | MB |",
      "|---|---|---|---|---|---:|"]
for r in res:
    ind = ", ".join(f"{k}×{v}" for k, v in (r["alto"] + r["medio"]).most_common(4)) or "—"
    md.append(f"| `{r['nome']}` | **{r['veredito']}** | {'SIM' if r['debug'] else 'não'} | {ind} | "
              f"{', '.join(sorted(r['perms'] & PERMS_GRAVES)) or '—'} | {r['mb']:.0f} |")
for r in res:
    md += ["", f"## `{r['nome']}` — veredito {r['veredito']}"]
    if r["erro"]:
        md.append(f"- Erro de leitura: {r['erro']}")
    md.append(f"- Assinado com certificado de depuração (build caseiro, fora de loja): {'SIM' if r['debug'] else 'não'}")
    if r["alto"] or r["medio"]:
        md.append("- Termos de mineração: " + ", ".join(f"`{k}`×{v}" for k, v in (r["alto"] + r["medio"]).most_common(12)))
    if r["perms"]:
        md.append("- Permissões/privilégios: " + ", ".join(sorted(r["perms"])))
    if r["limites"]:
        md.append("- Mexe com limites de hardware/benchmark: " + ", ".join(f"`{k}`×{v}" for k, v in r["limites"].most_common(12)))
    if r["hosts"]:
        md.append("- Servidores no código: " + ", ".join(h for h, _ in r["hosts"].most_common(15)))
    if r["libs"]:
        md.append("- Bibliotecas nativas: " + ", ".join(sorted(r["libs"])[:25]))
print("\n".join(md))
if SAIDA:
    os.makedirs(os.path.dirname(os.path.abspath(SAIDA)), exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\n(salvo em {SAIDA})")
