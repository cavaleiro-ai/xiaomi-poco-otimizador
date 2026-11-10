# -*- coding: utf-8 -*-
"""Varredura profunda SOMENTE LEITURA de um Android via ADB.
Não escreve, não edita e não apaga nada no aparelho. A única exceção é o 'adb bugreport',
em que o próprio Android gera um arquivo zip temporário (comportamento padrão do sistema).

Uso:
  python coletar.py <pasta_saida> [--rapido] [--sem-bugreport]

  --rapido         pula as partes demoradas (conteúdo de todos os .rc/.conf, varredura de /sys,
                   dropbox completo, dumpsys de todos os serviços, appops por app e bugreport).
                   Leva de 3 a 8 minutos; a completa leva de 20 a 60 minutos.
  --sem-bugreport  faz tudo, menos o bugreport (o bugreport traz o log térmico interno e
                   a saúde do armazenamento em vários aparelhos; vale a pena gerar).

A pasta gerada contém DADOS PESSOAIS (lista de apps, logs, notificações de sistema).
Guarde no seu computador e não publique.
"""
import os
import re
import subprocess
import sys
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _adb  # noqa: E402

_adb.utf8_stdout()
_adb.ajuda(__doc__)
args = [a for a in sys.argv[1:] if not a.startswith("--")]
if not args:
    print(__doc__)
    sys.exit(1)
OUT = _adb.caminho_local(args[0])
RAPIDO = "--rapido" in sys.argv
SEM_BR = "--sem-bugreport" in sys.argv or RAPIDO
_adb.require_device()

DIRS = ["00_identidade", "01_props", "02_settings", "03_dumpsys", "04_sysfs", "05_proc", "06_fs_scripts_configs",
        "07_apps", "08_processos", "09_logs", "10_bugreport"]
for d in DIRS:
    os.makedirs(os.path.join(OUT, d), exist_ok=True)
LOG = open(os.path.join(OUT, "_coleta.log"), "a", encoding="utf-8")
with open(os.path.join(OUT, "_LEIA-ME.txt"), "w", encoding="utf-8") as f:
    f.write("Esta pasta foi gerada por coletar.py (somente leitura) e contém dados pessoais do aparelho:\n"
            "lista de apps, logs do sistema, estatísticas de uso. Não publique nem envie a terceiros.\n")
t0 = time.time()


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.write(line + "\n")
    LOG.flush()


def save(rel, data):
    p = os.path.join(OUT, rel)
    with open(p, "wb") as f:
        f.write(data if isinstance(data, bytes) else data.encode("utf-8", "replace"))


def run_local(rel, timeout, *adb_args):
    log(f"{rel} <- adb {' '.join(adb_args)}")
    rc, out, err = _adb.adb(*adb_args, timeout=timeout, binary=True)
    save(rel, out + (b"\n#stderr: " + err.encode() if err.strip() else b""))
    if rc != 0:
        log(f"   (rc={rc}) {rel}")


def dsh(rel, timeout, cmd):
    log(f"{rel}")
    rc, out, err = _adb.adb("shell", cmd, timeout=timeout, binary=True)
    save(rel, out)
    if rc not in (0, 1):
        log(f"   (rc={rc}) {rel} {err.strip()[:120]}")


# despeja 1 nível de arquivos de cada diretório passado (com timeout por arquivo), no aparelho
D1 = ('d1(){ for d in "$@"; do [ -d "$d" ] || continue; echo "#### $d"; for f in "$d"/*; do '
      'if [ -f "$f" ]; then echo "== $f"; timeout 2 head -c 4000 "$f" 2>&1; echo; fi; done; done; }; ')

log(f"=== INÍCIO da coleta ({'rápida' if RAPIDO else 'completa'}) em {OUT} ===")

# ---------- 00 identidade ----------
I = "00_identidade"
run_local(f"{I}/adb_version.txt", 20, "version")
run_local(f"{I}/adb_devices.txt", 20, "devices", "-l")
PROPS_ID = ("ro.product.brand ro.product.manufacturer ro.product.model ro.product.device ro.product.name "
            "ro.product.marketname ro.build.fingerprint ro.build.version.release ro.build.version.sdk "
            "ro.build.version.incremental ro.build.version.security_patch ro.miui.ui.version.name "
            "ro.mi.os.version.name ro.build.version.oneui ro.build.date ro.boot.verifiedbootstate ro.boot.flash.locked "
            "ro.secure ro.debuggable ro.board.platform ro.hardware ro.soc.model ro.soc.manufacturer ro.boot.hardware.sku "
            "ro.bootloader ro.vendor.build.date")
dsh(f"{I}/modelo.txt", 30, f'for p in {PROPS_ID}; do echo "$p = $(getprop $p)"; done')
dsh(f"{I}/uname_id.txt", 30, "uname -a; echo; id; echo; uptime; echo; cat /proc/version; echo; date")
dsh(f"{I}/root_check.txt", 40, 'echo "--- su:"; command -v su 2>&1; ls -la /sbin/su /system/bin/su /system/xbin/su 2>&1; '
    'echo "--- magisk:"; ls -la /data/adb 2>&1; echo "--- selinux:"; getenforce 2>&1')

# ---------- 01 props ----------
dsh("01_props/getprop.txt", 60, "getprop")
dsh("01_props/build_props_files.txt", 60,
    'for f in /system/build.prop /system/product/build.prop /system/system_ext/build.prop /vendor/build.prop '
    '/vendor/default.prop /odm/etc/build.prop /product/etc/build.prop /system_ext/etc/build.prop /mi_ext/etc/build.prop; '
    'do if [ -f "$f" ]; then echo "===== $f"; cat "$f" 2>&1; echo; fi; done')

# ---------- 02 settings ----------
T = "02_settings"
dsh(f"{T}/system.txt", 60, "settings list system")
dsh(f"{T}/secure.txt", 60, "settings list secure")
dsh(f"{T}/global.txt", 60, "settings list global")
dsh(f"{T}/device_config_flags.txt", 120, "cmd device_config list 2>&1")
dsh(f"{T}/overlays_rro.txt", 60, "cmd overlay list 2>&1")
dsh(f"{T}/features.txt", 60, "pm list features")

# ---------- 03 dumpsys ----------
S = "03_dumpsys"
EXPL = [
    ("zz_batterystats_checkin.txt", 300, "dumpsys batterystats --checkin"),
    ("zz_batterystats_full.txt", 300, "dumpsys batterystats"),
    ("zz_procstats_24h.txt", 120, "dumpsys procstats --hours 24"),
    ("zz_meminfo.txt", 120, "dumpsys meminfo"),
    ("zz_activity_processes.txt", 120, "dumpsys activity processes"),
    ("zz_activity_services.txt", 120, "dumpsys activity services"),
    ("zz_package_all.txt", 300, "dumpsys package packages"),
    ("zz_display_all.txt", 60, "dumpsys display"),
    ("zz_surfaceflinger.txt", 60, "dumpsys SurfaceFlinger"),
    ("zz_thermal.txt", 60, "dumpsys thermalservice"),
    ("zz_power.txt", 60, "dumpsys power"),
    ("zz_battery.txt", 30, "dumpsys battery"),
    ("zz_game.txt", 60, "dumpsys game; echo ----; cmd game list-modes"),
    ("zz_alarm.txt", 120, "dumpsys alarm"),
    ("zz_jobscheduler.txt", 120, "dumpsys jobscheduler"),
    ("zz_deviceidle.txt", 60, "dumpsys deviceidle"),
    ("zz_usagestats.txt", 180, "dumpsys usagestats"),
    ("zz_appops.txt", 180, "dumpsys appops"),
    ("zz_storaged.txt", 60, "dumpsys storaged"),
    ("zz_diskstats.txt", 60, "dumpsys diskstats"),
    ("zz_cpuinfo.txt", 60, "dumpsys cpuinfo"),
    ("zz_media_camera.txt", 120, "dumpsys media.camera"),
    ("zz_device_policy.txt", 60, "dumpsys device_policy"),
    ("zz_gfxinfo.txt", 180, "dumpsys gfxinfo"),
]
for name, t, cmd in EXPL:
    dsh(f"{S}/{name}", t, cmd + " 2>&1")
if not RAPIDO:
    dsh(f"{S}/_dumpsys_l.txt", 60, "dumpsys -l")
    # serviços que guardam dados pessoais (contas, mensagens, localização, biometria...) são pulados
    EXCL = re.compile(r"^(account|content|notification|wifi.*|telephony.*|telecom|phone|isms|iphonesubinfo|imms|isub|"
                      r"simphonebook|location|country_detector|lock_settings|trust|fingerprint|biometric|face|iris|backup|"
                      r"clipboard|textclassification|autofill|bluetooth.*|media_session|media_router|contexthub|keystore.*|"
                      r"credstore|voiceinteraction|search|print|textservices|sip|password_policy|companiondevice|people|"
                      r"sms.*|contacts.*|calendar.*|email.*|incremental)$")
    with open(os.path.join(OUT, S, "_dumpsys_l.txt"), encoding="utf-8", errors="replace") as f:
        svcs = sorted({l.strip() for l in f if l.strip() and not l.startswith("Currently running")})
    for svc in svcs:
        if EXCL.match(svc):
            log(f"   (pulado por privacidade) {svc}")
            continue
        safe = re.sub(r"[/:@ ]", "_", svc)
        dsh(f"{S}/{safe}.txt", 120, f"dumpsys {_adb.q(svc)} 2>&1")

# ---------- 04 sysfs ----------
Y = "04_sysfs"
dsh(f"{Y}/power_supply.txt", 300, D1 + "d1 /sys/class/power_supply/*")
dsh(f"{Y}/thermal_zones_cooling.txt", 600, D1 + "d1 /sys/class/thermal/*")
dsh(f"{Y}/cpu.txt", 300, D1 + "d1 /sys/devices/system/cpu/cpufreq/policy* /sys/devices/system/cpu/cpu[0-9]*/core_ctl "
    "/sys/devices/system/cpu/cpu_boost")
dsh(f"{Y}/gpu.txt", 300, D1 + "d1 /sys/class/kgsl/kgsl-3d0 /sys/class/kgsl/kgsl-3d0/devfreq /sys/class/misc/mali0/device "
    "/sys/kernel/gpu /sys/kernel/ged/hal /sys/module/mali_kbase/parameters")
dsh(f"{Y}/devfreq.txt", 300, D1 + "d1 /sys/class/devfreq/*")
dsh(f"{Y}/display_backlight.txt", 300, D1 + "d1 /sys/class/backlight/* /sys/class/leds/*backlight* /sys/class/mi_display/* "
    "/sys/class/drm/card0-DSI-1 /sys/devices/virtual/mi_display/*")
dsh(f"{Y}/storage_health_find.txt", 300,
    'for f in /sys/devices/virtual/mi_memory/mi_memory_device/ufshcd0/dump_health_desc; do [ -r "$f" ] && echo "== $f" && cat "$f"; done; '
    'find /sys/devices /sys/class/block -type f \\( -iname "pre_eol_info" -o -iname "life_time*" -o -iname "eol_info" '
    '-o -iname "life_time_estimation*" \\) 2>/dev/null | while IFS= read -r f; do echo "== $f"; timeout 2 cat "$f" 2>&1; done')
if not RAPIDO:
    dsh(f"{Y}/regulators_tensao.txt", 600, D1 + "d1 /sys/class/regulator/*")
    dsh(f"{Y}/module_parameters.txt", 600, D1 + "d1 /sys/module/*/parameters")
    KW = ("throttl aging burn lifetime life_time eol cycle_count soh health charge_full charge_control constant_charge "
          "input_current input_suspend voltage_max fastcharg fast_charg mitigat degrad derat smart_batt smart_chg "
          "night_charg restrict max_freq min_freq boost step_chg jeita batt_age batt_soh batt_cycle bms limit cap_learn "
          "learned design dim hbm flicker refresh fps panel brightness thermal temp ovp vbus vbat ibat icl fcc "
          "vfloat term_curr resistance esr impedance cutoff").split()
    expr = " -o ".join(f'-iname "*{k}*"' for k in KW)
    dsh(f"{Y}/keyword_find_sys.txt", 900,
        f'find /sys/devices /sys/class /sys/kernel /sys/module /sys/power -type f \\( {expr} \\) 2>/dev/null | '
        f'grep -v "^/sys/kernel/debug" | sort | head -n 12000 | while IFS= read -r f; do echo "== $f"; '
        f'timeout 1 head -c 1000 "$f" 2>&1; echo; done')

# ---------- 05 proc ----------
dsh("05_proc/basico.txt", 90,
    'for f in /proc/cpuinfo /proc/meminfo /proc/version /proc/cmdline /proc/uptime /proc/loadavg /proc/stat /proc/vmstat '
    '/proc/swaps /proc/mounts /proc/pressure/cpu /proc/pressure/memory /proc/pressure/io /proc/zoneinfo /proc/diskstats '
    '/proc/partitions; do echo "===== $f"; timeout 5 cat "$f" 2>&1; echo; done')
dsh("05_proc/sysctl_vm.txt", 120, D1 + "d1 /proc/sys/vm")
dsh("05_proc/df.txt", 30, "df -k 2>&1")

# ---------- 06 scripts e configs do sistema ----------
F_ = "06_fs_scripts_configs"
PARTS = "/system /vendor /product /odm /system_ext /mi_ext /oem /cust /vendor_dlkm /odm_dlkm"
FIND_SH = f'find {PARTS} -type f \\( -name "*.sh" -o -name "*.rc" \\) 2>/dev/null | sort'
dsh(f"{F_}/_lista_sh_rc.txt", 300, FIND_SH)
CFG_KW = ("thermal perf power batt charg display panel backlight brightness joyose powerkeeper cloud freq cpu gpu boost "
          "limit aging lifetime powerhint task_profiles sched memory lmk zram refresh fps game mitigat feature whitelist "
          "blacklist policy").split()
CFG_EXT = "xml json conf cfg ini txt prop sh rc config policy yaml csv list".split()
FIND_CFG = (f'find {PARTS} -type f \\( ' + " -o ".join(f'-iname "*{k}*"' for k in CFG_KW) + ' \\) \\( '
            + " -o ".join(f'-iname "*.{e}"' for e in CFG_EXT) + ' \\) 2>/dev/null | sort')
dsh(f"{F_}/_lista_configs.txt", 600, FIND_CFG)
dsh(f"{F_}/_tree_etc_bin_apps.txt", 300,
    'for d in /system/etc /vendor/etc /odm/etc /product/etc /system_ext/etc /mi_ext/etc /system/bin /vendor/bin '
    '/system/app /system/priv-app /product/app /product/priv-app /system_ext/app /system_ext/priv-app /vendor/app; '
    'do echo "########## $d"; ls -la "$d" 2>&1; done')
dsh(f"{F_}/sdcard_raiz.txt", 60, 'ls -la /sdcard 2>&1; echo; ls -la /sdcard/Android/media 2>&1; echo; ls -la /data/local/tmp 2>&1')
dsh(f"{F_}/sdcard_executaveis.txt", 600,
    'find /sdcard -type f \\( -iname "*.sh" -o -iname "*.apk" -o -iname "*.apks" -o -iname "*.xapk" -o -iname "*.dex" '
    '-o -iname "*.jar" -o -iname "*.so" -o -iname "*.js" -o -iname "*.py" -o -iname "*.bat" -o -iname "*.lua" \\) '
    '-not -path "*/.thumbnails/*" 2>/dev/null | head -n 6000 | while IFS= read -r f; do ls -la "$f" 2>&1; done')
if not RAPIDO:
    dsh(f"{F_}/conteudo_sh_rc.txt", 1200,
        FIND_SH + ' | while IFS= read -r f; do echo; echo "########## $f"; timeout 5 head -c 400000 "$f" 2>&1; done')
    dsh(f"{F_}/conteudo_configs.txt", 2400,
        FIND_CFG + ' | while IFS= read -r f; do echo; echo "########## $f"; ls -la "$f" 2>&1; timeout 5 head -c 300000 "$f" 2>&1; done')

# ---------- 07 apps ----------
A = "07_apps"
dsh(f"{A}/packages_all_f_u_i.txt", 120, "pm list packages -f -u -i 2>&1")
dsh(f"{A}/packages_system.txt", 60, "pm list packages -s 2>&1")
dsh(f"{A}/packages_third_party.txt", 60, "pm list packages -3 -i 2>&1")
dsh(f"{A}/packages_disabled.txt", 60, "pm list packages -d 2>&1")
dsh(f"{A}/packages_user0.txt", 60, "pm list packages --user 0 2>&1; echo ----; pm list users 2>&1")
dsh(f"{A}/accessibility_admin_roles.txt", 60,
    'echo "## accessibility"; settings get secure enabled_accessibility_services; echo "## owners"; dpm list-owners 2>&1; '
    'echo "## always-on vpn"; settings get secure always_on_vpn_app 2>&1; echo "## default roles"; '
    'for r in HOME ASSISTANT BROWSER DIALER SMS; do echo "$r: $(cmd role get-role-holders --user 0 android.app.role.$r 2>&1)"; done; '
    'echo "## teclado"; settings get secure default_input_method')
dsh(f"{A}/standby_buckets.txt", 300,
    'for p in $(pm list packages | sed "s/package://"); do echo "$p $(am get-standby-bucket $p 2>&1)"; done')
dsh(f"{A}/doze_whitelist.txt", 30, "dumpsys deviceidle whitelist")
if not RAPIDO:
    dsh(f"{A}/bg_restrictions_appops.txt", 600,
        'for p in $(pm list packages | sed "s/package://"); do echo "#### $p"; cmd appops get $p 2>&1; done')

# ---------- 08 processos ----------
P_ = "08_processos"
dsh(f"{P_}/ps_detalhado.txt", 60, "ps -A -o PID,PPID,USER,STAT,%CPU,TIME,RSS,VSZ,NI,PCY,NAME,ARGS 2>&1")
dsh(f"{P_}/top.txt", 120, "top -b -n 3 -d 3 2>&1")
dsh(f"{P_}/cpufreq_snapshot.txt", 90,
    'for i in 1 2 3 4 5 6; do date; for c in /sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq; do '
    'printf "%s " "$(cat $c 2>/dev/null)"; done; echo; cat /proc/loadavg; '
    'cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | tr "\\n" " "; echo; sleep 3; done')

# ---------- 09 logs ----------
L = "09_logs"
dsh(f"{L}/logcat_main_system_crash.txt", 240, "logcat -d -b main,system,crash -v threadtime 2>&1")
dsh(f"{L}/logcat_events.txt", 120, "logcat -d -b events -v threadtime 2>&1")
dsh(f"{L}/dmesg.txt", 60, "dmesg 2>&1")
dsh(f"{L}/dropbox_list.txt", 60, "dumpsys dropbox 2>&1")
if not RAPIDO:
    dsh(f"{L}/dropbox_print.txt", 900, "dumpsys dropbox --print 2>&1")

# ---------- 10 bugreport ----------
if not SEM_BR:
    log("Gerando bugreport (5 a 15 minutos; o celular pode esquentar um pouco)...")
    bdir = os.path.join(OUT, "10_bugreport")
    rc, out, err = _adb.adb("bugreport", bdir, timeout=1800)
    save("10_bugreport/_bugreport_stdout.txt", out + "\n" + err)
    zips = [z for z in os.listdir(bdir) if z.endswith(".zip")]
    for z in zips:
        try:
            with zipfile.ZipFile(os.path.join(bdir, z)) as zf:
                zf.extractall(os.path.join(bdir, "extracted"))
            log(f"bugreport extraído: 10_bugreport/extracted (de {z})")
        except zipfile.BadZipFile:
            log(f"   bugreport inválido: {z}")
    if not zips:
        log("   bugreport não foi gerado (veja 10_bugreport/_bugreport_stdout.txt)")

dur = (time.time() - t0) / 60
tam = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(OUT) for f in fs) / 1e6
log(f"=== FIM da coleta: {dur:.0f} min, {tam:.0f} MB em {OUT} ===")
