# -*- coding: utf-8 -*-
"""Restringe a atividade em segundo plano de apps pesados (equivale a "Restringir" em Bateria do app).
REVERSÍVEL: grava o modo anterior de cada app e gera um arquivo RESTAURAR.

Uso:
  python restringir_segundo_plano.py PACOTE [PACOTE ...] | --lista arq.txt   -> plano (nada é alterado)
  python restringir_segundo_plano.py ... --aplicar [--doze] [--forcar] [--registro PASTA]

  --doze     também tira o app da lista de isenção da economia de bateria (Doze), se estiver nela
  --forcar   permite restringir apps de mensagem, e-mail, banco e autenticação (eles atrasariam notificações,
             códigos de login e alertas de segurança; por isso são pulados por padrão)

Efeito: o app deixa de rodar serviços e tarefas agendadas quando não está aberto. Notificações push de
alta prioridade costumam continuar chegando. Se algo importante parar (ex.: upload do app de vídeo),
desfaça para aquele app.
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


APLICAR, DOZE, FORCAR = "--aplicar" in sys.argv, "--doze" in sys.argv, "--forcar" in sys.argv
REG = _adb.caminho_local(arg("--registro", "."))
valores = {arg(n) for n in ("--lista", "--registro") if arg(n)}
pacotes = [a for a in sys.argv[1:] if not a.startswith("--") and a not in valores]
if arg("--lista"):
    pacotes += [l.split("#", 1)[0].strip().split()[0] for l in _adb.ler_texto(arg("--lista")).splitlines()
                if l.split("#", 1)[0].strip()]
pacotes = list(dict.fromkeys(pacotes))
if not pacotes:
    print(__doc__)
    sys.exit(1)

# mensagens, e-mail, despertador, mobilidade: restringir atrasaria notificações e alarmes
NAO_ATRASAR = re.compile(r"whatsapp|telegram|signal|messenger|orca|discord|slack|teams|outlook|gmail|email|mail|"
                         r"android\.dialer|messaging|\.sms|alarm|clock|calendar|uber|99app|ifood|maps", re.I)

_adb.require_device()
inst = {l.replace("package:", "").strip() for l in _adb.sh("pm list packages --user 0", timeout=60).splitlines()}
doze_user = {l.split(",")[1] for l in _adb.sh("dumpsys deviceidle whitelist", timeout=30).splitlines()
             if l.startswith("user,") and l.count(",") >= 1}

plano, pulados = [], []
for p in pacotes:
    if p not in inst:
        pulados.append((p, "não instalado"))
    elif (NAO_ATRASAR.search(p) or _adb.categoria_sensivel(p)) and not FORCAR:
        cat = _adb.categoria_sensivel(p) or "mensagem/alarme"
        pulados.append((p, f"{cat}: restringir atrasaria notificações, códigos ou alertas (use --forcar se o dono confirmar)"))
    else:
        plano.append(p)


def modo(p, op):
    txt = _adb.sh(f"cmd appops get {p} {op}", timeout=20)
    m = re.search(rf"{op}: (\w+)", txt)
    return m.group(1) if m else "default"


print(f"Restrição de segundo plano ({'APLICANDO' if APLICAR else 'simulação, nada será alterado'}):")
for p in plano:
    extra = " + sair da isenção Doze" if DOZE and p in doze_user else ""
    print(f"  - {p}: hoje RUN_ANY_IN_BACKGROUND={modo(p, 'RUN_ANY_IN_BACKGROUND')}{extra}")
for p, m in pulados:
    print(f"  (pulado) {p}: {m}")
if not APLICAR:
    print("\nNada foi alterado. Para executar, repita com --aplicar (após autorização do dono).")
    sys.exit(0)

os.makedirs(REG, exist_ok=True)
carimbo = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
restp = os.path.join(REG, f"RESTAURAR_segundo_plano_{carimbo}.txt")
with open(restp, "w", encoding="utf-8") as rest:
    rest.write(f"# Para desfazer: rode cada linha com o celular conectado, ou: python restaurar.py \"{restp}\"\n")
    for p in plano:
        for op in ("RUN_ANY_IN_BACKGROUND", "RUN_IN_BACKGROUND"):
            antes = modo(p, op)
            _adb.adb("shell", f"cmd appops set {p} {op} ignore", timeout=20)
            rest.write(f"adb shell cmd appops set {p} {op} {antes}\n")
        if DOZE and p in doze_user:
            _adb.adb("shell", f"cmd deviceidle whitelist -{p}", timeout=20)
            rest.write(f"adb shell cmd deviceidle whitelist +{p}\n")
        print(f"  {p}: RUN_ANY_IN_BACKGROUND agora {modo(p, 'RUN_ANY_IN_BACKGROUND')}", flush=True)
print(f"\nPara desfazer: {restp}")
