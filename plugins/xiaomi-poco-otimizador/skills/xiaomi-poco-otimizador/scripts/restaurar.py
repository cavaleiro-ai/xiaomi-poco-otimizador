# -*- coding: utf-8 -*-
"""Executa um arquivo RESTAURAR_*.txt gerado pelos outros scripts (desfaz remoções, restrições e ajustes).

Uso:  python restaurar.py RESTAURAR_xxx.txt [--so PACOTE]     (--so restaura apenas aquele pacote)

Só executa comandos de desfazer:
  adb shell cmd package install-existing ...   (devolve um app removido para o usuário)
  adb install-multiple -r ...                  (reinstala do APK salvo; só roda se o app ainda estiver ausente)
  adb shell pm enable ...                      (reativa um app desativado)
  adb shell cmd appops set ...                 (devolve o modo de segundo plano anterior)
  adb shell cmd deviceidle whitelist ...       (devolve a isenção de economia de bateria)
  adb shell settings put global <escala de animação> ...
Qualquer outra linha é ignorada.
"""
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _adb  # noqa: E402

_adb.utf8_stdout()
_adb.ajuda(__doc__)
argv = sys.argv[1:]
SO = None
if "--so" in argv:
    i = argv.index("--so")
    SO = argv[i + 1] if i + 1 < len(argv) else None
    del argv[i:i + 2]
arquivos = [a for a in argv if not a.startswith("--")]
if not arquivos:
    print(__doc__)
    sys.exit(1)
PERMITIDO = re.compile(r"^adb (shell (cmd package install-existing|pm enable|cmd appops set|cmd deviceidle whitelist) |"
                       r"install-multiple -r |"
                       r"shell settings put global (window_animation_scale|transition_animation_scale|"
                       r"animator_duration_scale) [0-9.]+$)")
_adb.require_device()


def instalado(p):
    return f"package:{p}" in _adb.sh(f"pm list packages --user 0 {p}", timeout=30).split()


n = 0
for arq in arquivos:
    for ln in _adb.ler_texto(arq).splitlines():
        ln = ln.split("  #", 1)[0].strip()
        if not ln or ln.startswith("#"):
            continue
        if not PERMITIDO.match(ln):
            print(f"(ignorado, não é um comando de restauração) {ln}")
            continue
        partes = shlex.split(ln, posix=True)[1:]
        pac = re.search(r"([A-Za-z][\w]*(?:\.[\w]+)+)", " ".join(p for p in partes if not p.lower().endswith(".apk")))
        pac = pac.group(1) if pac else ""
        if partes[0] == "install-multiple":
            apks = [p for p in partes if p.lower().endswith(".apk")]
            pac = re.sub(r"[\\/][^\\/]+$", "", apks[0]).replace("\\", "/").rsplit("/", 1)[-1] if apks else ""
        if SO and SO not in (pac, pac.lstrip("+-")) and SO not in ln:
            continue
        if partes[0] == "install-multiple":
            if pac and instalado(pac):
                continue   # já voltou pelo install-existing
            faltando = [p for p in partes if p.lower().endswith(".apk") and not os.path.isfile(p)]
            if faltando:
                print(f"{ln}\n   -> APK salvo não encontrado: {faltando[0]}")
                continue
        rc, out, err = _adb.adb(*partes, timeout=600)
        print(f"{ln}\n   -> {(out + err).strip()[:200] or 'ok'}")
        n += 1
print(f"\n{n} comando(s) de restauração executados.")
