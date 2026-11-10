# -*- coding: utf-8 -*-
"""Resumo das câmeras do aparelho a partir do 'dumpsys media.camera'. SOMENTE LEITURA.

Mostra, por câmera do HAL: frente/trás, nível Camera2 (LEGACY/LIMITED/FULL/LEVEL_3), recursos (RAW,
controle manual), resolução do sensor exposta, maior JPEG, estabilização óptica/eletrônica, vídeo em
alta taxa de quadros e quais câmeras ficam ESCONDIDAS de apps de terceiros (só o app do fabricante usa).
Também lista os perfis de gravação de vídeo (CamcorderProfile) e as propriedades de câmera do sistema.

Uso:
  python resumo_camera.py                      (lê do aparelho conectado e salva os brutos em ./camera_bruto)
  python resumo_camera.py --arquivo dumpsys_media_camera.txt [--perfis media_profiles.xml]
  [--saida resumo_camera.md]
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _adb  # noqa: E402

_adb.utf8_stdout()
_adb.ajuda(__doc__)


def arg(nome, padrao=None):
    return sys.argv[sys.argv.index(nome) + 1] if nome in sys.argv else padrao


SAIDA = arg("--saida")
props_txt = ""
if arg("--arquivo"):
    with open(arg("--arquivo"), encoding="utf-8", errors="replace") as f:
        dump = f.read().replace("\r", "")
    perfis = ""
    if arg("--perfis"):
        with open(arg("--perfis"), encoding="utf-8", errors="replace") as f:
            perfis = f.read()
else:
    _adb.require_device()
    bruto = os.path.abspath("camera_bruto")
    os.makedirs(bruto, exist_ok=True)
    dump = _adb.sh("dumpsys media.camera", timeout=180)
    var = _adb.getprop("ro.media.xml_variant.profile")
    cands = ([f"/vendor/etc/media_profiles_{var}.xml"] if var else []) + \
        ["/vendor/etc/media_profiles_V1_0.xml", "/vendor/etc/media_profiles.xml", "/odm/etc/media_profiles_V1_0.xml",
         "/system/etc/media_profiles.xml"]
    perfis = ""
    for c in cands:
        perfis = _adb.sh(f"cat {c} 2>/dev/null", timeout=30)
        if "<MediaSettings" in perfis:
            perfis = f"<!-- {c} -->\n" + perfis
            break
    props_txt = _adb.sh("getprop | grep -iE 'camera|aux|privapp'", timeout=30)
    for nome, txt in [("dumpsys_media_camera.txt", dump), ("media_profiles.xml", perfis), ("props_camera.txt", props_txt)]:
        with open(os.path.join(bruto, nome), "w", encoding="utf-8") as f:
            f.write(txt)
    print(f"(brutos salvos em {bruto})")

NIVEL = {"0": "LIMITED", "1": "FULL", "2": "LEGACY", "3": "LEVEL_3", "4": "EXTERNAL"}
FMT = {"32": "RAW_SENSOR", "33": "JPEG", "34": "PRIVATE", "35": "YUV", "37": "RAW10", "38": "RAW12", "36": "RAW_OPAQUE"}

publicas = re.findall(r'Device (\d+) maps to "(\w+)"', dump)
ids_publicos = [x[1] for x in publicas]
n_total = re.search(r"Number of camera devices: (\d+)", dump)
n_norm = re.search(r"Number of normal camera devices: (\d+)", dump)

blocos = re.split(r"^== Camera HAL device (\S+) \(v[\d.]+\) static information: ==$", dump, flags=re.M)
cams = collections.OrderedDict()
for i in range(1, len(blocos) - 1, 2):
    nome, corpo = blocos[i], blocos[i + 1].split("dumpState: ==")[0]
    cid = nome.rsplit("/", 1)[-1]
    chaves = {}
    atual = None
    for ln in corpo.splitlines():
        m = re.match(r"^\s{4,8}([a-zA-Z][\w.]+) \([0-9a-f]+\): \w+\[\d+\]", ln)
        if m:
            atual = m.group(1)
            chaves[atual] = []
        elif atual and ln.strip().startswith("["):
            chaves[atual].append(ln.strip().strip("[]").strip())
    cams[cid] = chaves


def val(ch, k):
    return " ".join(ch.get(k, [])).strip()


linhas = []
for cid, ch in cams.items():
    face = val(ch, "android.lens.facing") or "?"
    nivel = NIVEL.get(val(ch, "android.info.supportedHardwareLevel"), val(ch, "android.info.supportedHardwareLevel") or "?")
    caps = val(ch, "android.request.availableCapabilities").split()
    pa = val(ch, "android.sensor.info.pixelArraySize").split()
    mp = int(pa[0]) * int(pa[1]) / 1e6 if len(pa) == 2 else 0
    jpeg, fmts = (0, 0), set()
    for ln in ch.get("android.scaler.availableStreamConfigurations", []):
        p = ln.split()
        if len(p) == 4 and p[3] == "OUTPUT":
            fmts.add(FMT.get(p[0], p[0]))
            if p[0] == "33" and int(p[1]) * int(p[2]) > jpeg[0] * jpeg[1]:
                jpeg = (int(p[1]), int(p[2]))
    ois = "sim" if "1" in val(ch, "android.lens.info.availableOpticalStabilization").split() else "não"
    eis = val(ch, "android.control.availableVideoStabilizationModes").split()
    eis_txt = "sim" if "1" in eis else "não"
    if "2" in eis:
        eis_txt += " (+prévia)"
    hs = [int(x) for x in " ".join(ch.get("android.control.availableHighSpeedVideoConfigurations", [])).split() if x.isdigit()]
    alta = sorted({f"{hs[j]}x{hs[j + 1]}@{hs[j + 3]}" for j in range(0, len(hs) - 4, 5) if hs[j + 3] >= 60})
    focal = val(ch, "android.lens.info.availableFocalLengths")
    abert = val(ch, "android.lens.info.availableApertures")
    fis = val(ch, "android.logicalMultiCamera.physicalIds")
    linhas.append(dict(id=cid, publica="sim" if cid in ids_publicos else "ESCONDIDA", face=face, nivel=nivel,
                       mp=mp, pa="x".join(pa), jpeg=f"{jpeg[0]}x{jpeg[1]}" if jpeg[0] else "?",
                       raw="sim" if "RAW" in caps else "não", manual="sim" if "MANUAL_SENSOR" in caps else "não",
                       ois=ois, eis=eis_txt, alta=", ".join(alta) or "—", focal=focal, abert=abert,
                       logica="sim" if "LOGICAL_MULTI_CAMERA" in caps else "não", fis=fis))

md = ["# Resumo das câmeras", ""]
if n_total:
    md.append(f"Câmeras no HAL: {n_total.group(1)}; visíveis para apps comuns: {n_norm.group(1) if n_norm else '?'} "
              f"(IDs públicos: {', '.join(ids_publicos) or '?'}). As marcadas como ESCONDIDA só podem ser usadas pelo app de "
              f"câmera do fabricante ou por apps que ele libera numa lista interna (exige root para alterar).")
md += ["", "| ID | acesso | lado | nível Camera2 | sensor exposto | maior JPEG | RAW | manual | OIS | EIS | alta velocidade | focal (mm) | f/ |",
       "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for r in linhas:
    md.append(f"| {r['id']} | {r['publica']} | {r['face']} | {r['nivel']} | {r['pa']} ({r['mp']:.0f} MP) | {r['jpeg']} | "
              f"{r['raw']} | {r['manual']} | {r['ois']} | {r['eis']} | {r['alta']} | {r['focal']} | {r['abert']} |")

if perfis:
    md += ["", "## Perfis de gravação de vídeo (CamcorderProfile)",
           "É o que apps de terceiros conseguem gravar pelo caminho padrão; o app do fabricante pode ir além."]
    for m in re.finditer(r'<CamcorderProfiles\s+cameraId="(\d+)"(.*?)</CamcorderProfiles>', perfis, re.S):
        qs = re.findall(r'quality="(\w+)"', m.group(2))
        fps = re.findall(r'frameRate="(\d+)"', m.group(2))
        md.append(f"- câmera {m.group(1)}: {', '.join(dict.fromkeys(qs))} (taxas: {', '.join(sorted(set(fps), key=int))} fps)")
if props_txt:
    chave = [l for l in props_txt.splitlines() if re.search(r"aux|privapp|packagelist|zsl|hal3|camera\.disable", l, re.I)]
    if chave:
        md += ["", "## Propriedades de câmera relevantes", "```"] + chave[:40] + ["```"]

md += ["", "## Como interpretar",
       "- LEVEL_3 ou FULL com RAW e controle manual: aceita apps avançados (GCam/ports, apps de RAW manual).",
       "- 'Sensor exposto' menor que a resolução anunciada (ex.: 12 MP num sensor de 108 MP) significa que o modo de "
       "resolução total só existe no app do fabricante.",
       "- Sem OIS, fotos noturnas e vídeo dependem de EIS e de empilhamento de quadros: use apoio ou modo noite.",
       "- Câmeras ESCONDIDAS (ultra-angular, macro, profundidade) não aparecem em apps de terceiros sem root."]
print("\n".join(md))
if SAIDA:
    os.makedirs(os.path.dirname(os.path.abspath(SAIDA)), exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"\n(salvo em {SAIDA})")
