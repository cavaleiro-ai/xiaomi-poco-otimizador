# -*- coding: utf-8 -*-
"""Remove apps de forma REVERSÍVEL com 'pm uninstall -k --user 0': o app some para o usuário e os dados ficam.
  - Apps de sistema (de fábrica): o APK continua na partição do sistema e volta com 'cmd package install-existing'.
  - Apps instalados pelo usuário: o Android pode apagar o APK. Por isso o script SEMPRE copia os APKs desses
    apps antes (para --backup-apks, ou <registro>/apks) e o RESTAURAR reinstala a partir dessa cópia se preciso.
Se o sistema recusar a remoção, desativa com 'pm disable-user'. Nunca usa remoção completa, root ou
alteração de partições.

Uso:
  python remover_pacotes.py PACOTE [PACOTE ...]          -> só mostra o plano (nada é alterado)
  python remover_pacotes.py --lista pacotes.txt          -> idem, lendo um pacote por linha (# = comentário)
  python remover_pacotes.py ... --aplicar [--backup-apks PASTA] [--registro PASTA]

  --aplicar          executa de verdade (peça autorização explícita do dono antes)
  --backup-apks DIR  pasta para as cópias dos APKs (padrão: <registro>/apks). Apps do usuário são sempre
                     copiados; com esta opção, os de sistema também.
  --registro DIR     onde gravar o log e o arquivo RESTAURAR (padrão: pasta atual)

Pacotes protegidos (sistema, telefone, Play, teclado e launcher em uso, segurança do fabricante) são
recusados mesmo que estejam na lista: removê-los pode travar o aparelho em loop de inicialização ou
impedir o uso do telefone.
"""
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


APLICAR = "--aplicar" in sys.argv
BACKUP = arg("--backup-apks")
REG = _adb.caminho_local(arg("--registro", "."))
valores = {arg(n) for n in ("--lista", "--backup-apks", "--registro") if arg(n)}
pacotes = [a for a in sys.argv[1:] if not a.startswith("--") and a not in valores]
if arg("--lista"):
    for ln in _adb.ler_texto(arg("--lista")).splitlines():
        ln = ln.split("#", 1)[0].strip()
        if ln:
            pacotes.append(ln.split()[0])
pacotes = list(dict.fromkeys(pacotes))
if not pacotes:
    print(__doc__)
    sys.exit(1)

PROTEGIDOS = {
    # Android / AOSP
    "android", "com.android.systemui", "com.android.settings", "com.android.phone", "com.android.server.telecom",
    "com.android.shell", "com.android.packageinstaller", "com.google.android.packageinstaller",
    "com.android.permissioncontroller", "com.google.android.permissioncontroller", "com.android.externalstorage",
    "com.android.mtp", "com.android.documentsui", "com.google.android.documentsui", "com.android.keychain",
    "com.android.location.fused", "com.android.bluetooth", "com.android.nfc", "com.android.se",
    "com.android.inputdevices", "com.android.incallui", "com.android.dialer", "com.google.android.dialer",
    "com.android.emergency", "com.google.android.cellbroadcastreceiver", "com.android.cellbroadcastreceiver",
    "com.android.webview", "com.google.android.webview", "com.google.android.trichromelibrary",
    "com.android.wallpaperbackup", "com.android.certinstaller", "com.android.networkstack.tethering",
    "com.android.launcher3", "com.google.android.ext.services", "com.android.ext.services",
    # Google
    "com.google.android.gms", "com.google.android.gsf", "com.android.vending", "com.google.android.inputmethod.latin",
    "com.google.android.apps.nexuslauncher", "com.google.android.setupwizard",
    # Xiaomi / POCO / Redmi
    "com.miui.home", "com.mi.android.globallauncher", "com.miui.securitycenter", "com.miui.securitycore",
    "com.miui.securityadd", "com.miui.powerkeeper", "com.xiaomi.finddevice", "com.miui.daemon", "com.xiaomi.xmsf",
    "com.miui.guardprovider", "com.xiaomi.account", "com.miui.core", "com.miui.system", "com.miui.rom",
    "com.lbe.security.miui", "com.miui.packageinstaller", "com.xiaomi.misettings", "com.miui.miwallpaper",
    "com.android.updater", "com.miui.permission", "com.xiaomi.mi_connect_service",
    # Samsung
    "com.sec.android.app.launcher", "com.samsung.android.honeyboard", "com.samsung.android.dialer",
    "com.samsung.android.incallui", "com.sec.android.app.SecSetupWizard", "com.samsung.android.lool",
    "com.samsung.android.providers.context", "com.sec.android.app.personalization",
    # Motorola / outros launchers e teclados de fábrica
    "com.samsung.android.game.gos",
    "com.motorola.launcher3", "com.oplus.launcher", "com.oppo.launcher", "com.coloros.safecenter",
    "com.huawei.android.launcher", "com.swiftkey.swiftkeyconfigurator", "com.touchtype.swiftkey",
}
PREFIXOS = ("com.android.providers.", "com.google.android.providers.", "com.android.networkstack",
            "com.google.android.networkstack", "com.android.server.", "com.qualcomm.qti.telephony",
            "com.android.phone.", "com.android.ims", "org.codeaurora.ims", "com.android.cts.", "android.auto_generated",
            "com.samsung.android.knox", "com.sec.enterprise", "com.samsung.knox")

_adb.require_device()
dinamicos = set()
for role in ("HOME", "SMS", "DIALER"):
    txt = _adb.sh(f"cmd role get-role-holders --user 0 android.app.role.{role}", timeout=20)
    dinamicos.update(x.strip() for x in re.split(r"[;\s]+", txt) if "." in x)
# Android 8–9 não tem 'cmd role': descobre o launcher pela atividade que responde ao botão Início
home = _adb.sh("cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME",
               timeout=20).strip().splitlines()
if home and "/" in home[-1]:
    dinamicos.add(home[-1].split("/")[0].strip())
ime = _adb.sh("settings get secure default_input_method", timeout=20).strip()
if "/" in ime:
    dinamicos.add(ime.split("/")[0])
wv = re.search(r"Current WebView package \(name, version\): \((\S+?),", _adb.sh("dumpsys webviewupdate", timeout=30))
if wv:
    dinamicos.add(wv.group(1))

usuario = {l.replace("package:", "").strip() for l in _adb.sh("pm list packages --user 0", timeout=60).splitlines()}
todos = {l.replace("package:", "").strip() for l in _adb.sh("pm list packages -u", timeout=60).splitlines()}
desativ = {l.replace("package:", "").strip() for l in _adb.sh("pm list packages -d", timeout=60).splitlines()}
terceiros = {l.replace("package:", "").strip() for l in _adb.sh("pm list packages -3", timeout=60).splitlines()}

plano, bloq, ausentes, ja = [], [], [], []
for p in pacotes:
    if p in PROTEGIDOS or p.startswith(PREFIXOS) or p in dinamicos:
        motivo = "em uso como launcher/teclado/SMS/telefone/WebView" if p in dinamicos else "pacote essencial"
        bloq.append((p, motivo))
    elif p not in todos:
        ausentes.append(p)
    elif p not in usuario:
        ja.append(p)
    else:
        plano.append(p)

print(f"Plano de remoção reversível ({'APLICANDO' if APLICAR else 'simulação, nada será alterado'}):")
print(f"  remover para o usuário: {len(plano)}")
for p in plano:
    extra = " [instalado pelo usuário: o APK será copiado antes]" if p in terceiros else ""
    print(f"    - {p}{' (já desativado)' if p in desativ else ''}{extra}")
if bloq:
    print(f"  RECUSADOS por segurança: {len(bloq)}")
    for p, m in bloq:
        print(f"    - {p}: {m}")
if ja:
    print(f"  já removidos para o usuário: {', '.join(ja)}")
if ausentes:
    print(f"  não instalados neste aparelho: {', '.join(ausentes)}")
if not APLICAR:
    print("\nNada foi alterado. Para executar, repita o comando com --aplicar (após autorização do dono).")
    sys.exit(0)

os.makedirs(REG, exist_ok=True)
carimbo = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
logp = os.path.join(REG, f"remocao_{carimbo}.log")
restp = os.path.join(REG, f"RESTAURAR_pacotes_{carimbo}.txt")
antes = len(usuario)
ok = falhas = 0
with open(logp, "w", encoding="utf-8") as log, open(restp, "w", encoding="utf-8") as rest:
    rest.write("# Para desfazer: rode cada linha num terminal com o celular conectado,\n"
               f"# ou use: python restaurar.py \"{restp}\"\n")
    pasta_apks = _adb.caminho_local(BACKUP) if BACKUP else os.path.join(REG, "apks")
    for p in plano:
        n_apk, salvos = 0, []
        if BACKUP or p in terceiros:
            caminhos = [l.replace("package:", "").strip() for l in _adb.sh(f"pm path {p}", timeout=30).splitlines()
                        if l.startswith("package:")]
            d = os.path.join(pasta_apks, p)
            os.makedirs(d, exist_ok=True)
            for c in caminhos:
                destino = os.path.join(d, os.path.basename(c))
                rc, _, _ = _adb.adb("pull", c, destino, timeout=1800)
                if rc == 0 and os.path.isfile(destino):
                    n_apk += 1
                    salvos.append(destino)
            if p in terceiros and (not caminhos or n_apk < len(caminhos)):
                linha = f"{p:55s} PULADO: não foi possível copiar o APK antes de remover (app do usuário)"
                print(linha, flush=True)
                log.write(linha + "\n")
                falhas += 1
                continue
        rc, out, err = _adb.adb("shell", f"pm uninstall -k --user 0 {p}", timeout=60)
        res = (out + err).strip().splitlines()[-1:] or [""]
        if "Success" in res[0]:
            rest.write(f"adb shell cmd package install-existing --user 0 {p}\n")
            if salvos:   # reinstalação a partir da cópia; o restaurar.py só usa se o app continuar ausente
                arqs = " ".join('"' + x.replace("\\", "/") + '"' for x in salvos)
                rest.write(f"adb install-multiple -r {arqs}\n")
            acao = "removido para o usuário"
            ok += 1
        else:
            rc2, out2, err2 = _adb.adb("shell", f"pm disable-user --user 0 {p}", timeout=60)
            r2 = (out2 + err2).strip()
            if "disabled" in r2.lower():
                rest.write(f"adb shell pm enable --user 0 {p}\n")
                acao = f"desativado (remoção recusada: {res[0]})"
                ok += 1
            else:
                acao = f"FALHOU: {res[0]} / {r2[:120]}"
                falhas += 1
        linha = f"{p:55s} {acao}" + (f"  [APKs salvos: {n_apk}]" if salvos else "")
        print(linha, flush=True)
        log.write(linha + "\n")
    depois = len([l for l in _adb.sh("pm list packages --user 0", timeout=60).splitlines() if l.strip()])
    resumo = f"\nConcluído: {ok} ok, {falhas} falhas. Pacotes do usuário: {antes} -> {depois}."
    print(resumo)
    log.write(resumo + "\n")
print(f"Log: {logp}\nPara desfazer: {restp}")
print("Reinicie o aparelho e use-o normalmente; se algo essencial deixar de funcionar, restaure o pacote correspondente.")
