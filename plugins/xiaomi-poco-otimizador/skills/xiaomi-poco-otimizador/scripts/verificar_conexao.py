# -*- coding: utf-8 -*-
"""Confere o adb e a conexão com o celular e mostra a identidade do aparelho.
SOMENTE LEITURA. Uso:  python verificar_conexao.py [--testar-escrita]

--testar-escrita  verifica se o ADB pode alterar configurações (necessário para ajustar
                  animações). Regrava o MESMO valor atual de window_animation_scale,
                  portanto não muda nada no aparelho. Use apenas na fase de aplicação.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _adb  # noqa: E402

_adb.utf8_stdout()
_adb.ajuda(__doc__)
testar_escrita = "--testar-escrita" in sys.argv

adb = _adb.need_adb()
rc, ver, _ = _adb.adb("version", timeout=20)
print("adb:", " ".join(adb))
print((ver.splitlines() or ["?"])[0])
rc, devs, _ = _adb.adb("devices", "-l", timeout=20)
print("\n" + devs.strip())

st = _adb.state()
if st != "device":
    print(f"\nESTADO: {st}\n{_adb.GUIA_ESTADO.get(st, '')}")
    sys.exit(2)

props = {}
for p in ["ro.product.brand", "ro.product.manufacturer", "ro.product.model", "ro.product.marketname",
          "ro.product.vendor.marketname", "ro.product.device", "ro.build.version.release", "ro.build.version.sdk",
          "ro.build.version.security_patch", "ro.build.display.id", "ro.mi.os.version.name",
          "ro.miui.ui.version.name", "ro.build.version.oneui", "ro.soc.manufacturer", "ro.soc.model",
          "ro.board.platform", "ro.boot.verifiedbootstate", "ro.boot.flash.locked", "persist.security.adbinput"]:
    props[p] = _adb.getprop(p)

nome = props["ro.product.marketname"] or props["ro.product.vendor.marketname"] or props["ro.product.model"]
print("\n== Aparelho ==")
print(f"Marca/fabricante : {props['ro.product.brand']} / {props['ro.product.manufacturer']}")
print(f"Modelo           : {nome}  (modelo {props['ro.product.model']}, codinome {props['ro.product.device']})")
print(f"Android          : {props['ro.build.version.release']} (SDK {props['ro.build.version.sdk']}), "
      f"patch de segurança {props['ro.build.version.security_patch']}")
skin = props["ro.mi.os.version.name"] and f"HyperOS {props['ro.mi.os.version.name']}" \
    or props["ro.miui.ui.version.name"] and f"MIUI {props['ro.miui.ui.version.name']}" \
    or props["ro.build.version.oneui"] and f"One UI {props['ro.build.version.oneui']}" or ""
print(f"Sistema          : {props['ro.build.display.id']} {('— ' + skin) if skin else ''}")
print(f"Processador      : {props['ro.soc.manufacturer']} {props['ro.soc.model']} ({props['ro.board.platform']})")
print(f"Bootloader       : {'bloqueado' if props['ro.boot.flash.locked'] == '1' else 'DESBLOQUEADO' if props['ro.boot.flash.locked'] == '0' else '?'}"
      f" (verifiedboot={props['ro.boot.verifiedbootstate'] or '?'})")
su = _adb.sh("command -v su 2>/dev/null; ls /data/adb/magisk 2>/dev/null | head -1", timeout=20).strip()
print(f"Root             : {'indícios de root: ' + su if su else 'não detectado (normal)'}")

xiaomi = props["ro.product.manufacturer"].lower() in ("xiaomi", "redmi", "poco") or bool(props["ro.miui.ui.version.name"] or props["ro.mi.os.version.name"])
if xiaomi:
    print("\n== Xiaomi/POCO/Redmi ==")
    print("Família Xiaomi detectada: leia references/xiaomi_hyperos.md.")
    sec = props["persist.security.adbinput"]
    print(f"'Depuração USB (configurações de segurança)': {'ligada' if sec == '1' else 'desligada ou desconhecida'} "
          f"(persist.security.adbinput={sec or 'vazio'}). Sem ela o ADB não altera configurações nem simula toques.")

if testar_escrita:
    cur = _adb.sh("settings get global window_animation_scale", timeout=20).strip()
    # regrava exatamente o valor atual; se a chave não existir ("null"), grava o padrão do Android (1.0)
    val = cur if cur and cur != "null" else "1.0"
    rc, out, err = _adb.adb("shell", f"settings put global window_animation_scale {val}", timeout=20)
    txt = (out + err).strip()
    ok = rc == 0 and "Exception" not in txt
    print(f"\nTeste de escrita de configurações (regravou o valor atual {val}): {'PERMITIDO' if ok else 'BLOQUEADO'}")
    if not ok:
        print("  ->", (txt.splitlines() or [''])[-1][:200])
        if xiaomi:
            print("  Xiaomi: ligue 'Depuração USB (configurações de segurança)' em Opções do desenvolvedor "
                  "(exige conta Xiaomi e chip SIM) ou faça os ajustes pela tela.")
print("\nConexão OK.")
