# -*- coding: utf-8 -*-
"""Funções comuns a todos os scripts: localizar o adb, rodar comandos no aparelho,
conferir a conexão e escrever saída em UTF-8 (Windows, macOS e Linux).

Somente a biblioteca padrão do Python 3.8+ é usada.
Variáveis de ambiente aceitas:
  ADB            caminho completo do executável adb (se não estiver no PATH)
  ANDROID_SERIAL serial do aparelho, quando houver mais de um conectado (padrão do próprio adb)
  ADB_WRAPPER    (só para testes) comando que substitui o adb, ex.: "python fake_adb.py"
"""
import os
import shlex
import shutil
import subprocess
import sys
import time


def utf8_stdout():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _candidatos():
    home = os.path.expanduser("~")
    c = []
    if os.name == "nt":
        la = os.environ.get("LOCALAPPDATA", "")
        c += [os.path.join(la, "Android", "Sdk", "platform-tools", "adb.exe"),
              r"C:\platform-tools\adb.exe",
              r"C:\adb\adb.exe",
              os.path.join(home, "platform-tools", "adb.exe"),
              os.path.join(home, "Downloads", "platform-tools", "adb.exe")]
        wg = os.path.join(la, "Microsoft", "WinGet", "Packages")
        if os.path.isdir(wg):
            for d in os.listdir(wg):
                if d.lower().startswith("google.platformtools"):
                    c.append(os.path.join(wg, d, "platform-tools", "adb.exe"))
        sc = os.path.join(home, "scoop", "apps", "adb", "current", "platform-tools", "adb.exe")
        c.append(sc)
    else:
        c += [os.path.join(home, "Library", "Android", "sdk", "platform-tools", "adb"),
              os.path.join(home, "Android", "Sdk", "platform-tools", "adb"),
              os.path.join(home, "platform-tools", "adb"),
              os.path.join(home, "Downloads", "platform-tools", "adb"),
              "/opt/homebrew/bin/adb", "/usr/local/bin/adb", "/usr/bin/adb"]
    return c


def find_adb():
    """Devolve a lista de argumentos que invoca o adb, ou None."""
    w = os.environ.get("ADB_WRAPPER")
    if w:
        return shlex.split(w, posix=(os.name != "nt"))
    env = os.environ.get("ADB")
    if env and os.path.isfile(env):
        return [env]
    p = shutil.which("adb")
    if p:
        return [p]
    for cand in _candidatos():
        if os.path.isfile(cand):
            return [cand]
    return None


ADB = find_adb()

INSTRUCOES_SEM_ADB = """
O programa 'adb' (Android Platform Tools) não foi encontrado neste computador.
Instale e tente de novo:
  Windows : winget install Google.PlatformTools      (ou baixe em https://developer.android.com/tools/releases/platform-tools)
  macOS   : brew install android-platform-tools
  Linux   : sudo apt install adb      (Debian/Ubuntu)   |   sudo dnf install android-tools (Fedora)
Se já estiver instalado fora do PATH, defina a variável ADB com o caminho completo do adb.
"""


def need_adb():
    if not ADB:
        print(INSTRUCOES_SEM_ADB, file=sys.stderr)
        sys.exit(3)
    return ADB


def adb(*args, timeout=120, input=None, binary=False):
    """Roda 'adb <args>' e devolve (returncode, stdout, stderr). Nunca levanta exceção de timeout."""
    need_adb()
    try:
        r = subprocess.run(ADB + list(args), input=input, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        out = e.stdout or b""
        return 124, (out if binary else out.decode("utf-8", "replace").replace("\r", "")), "timeout"
    out = r.stdout if binary else r.stdout.decode("utf-8", "replace").replace("\r", "")
    return r.returncode, out, r.stderr.decode("utf-8", "replace").replace("\r", "")


def sh(cmd, timeout=120, retries=1):
    """Roda um comando no shell do aparelho e devolve o texto (vazio em caso de falha)."""
    for tentativa in range(max(1, retries)):
        rc, out, err = adb("shell", cmd, timeout=timeout)
        if rc == 0 or out:
            return out
        if tentativa + 1 < retries:
            adb("wait-for-device", timeout=120)
            time.sleep(2)
    return ""


def getprop(name):
    return sh(f"getprop {name}", timeout=20).strip()


def state():
    rc, out, err = adb("get-state", timeout=20)
    s = (out or "").strip()
    if not s:
        e = (err or "").lower()
        if "unauthorized" in e:
            return "unauthorized"
        if "more than one" in e:
            return "multiple"
        if "offline" in e:
            return "offline"
        if "no permissions" in e or "insufficient permissions" in e:
            return "nopermission"
        return "none"
    return s


GUIA_ESTADO = {
    "none": "Nenhum aparelho encontrado. Confira: cabo USB que transmite dados (não só carga), "
            "'Depuração USB' ligada em Opções do desenvolvedor, modo USB 'Transferência de arquivos'. "
            "No Windows, pode faltar o driver USB do fabricante.",
    "unauthorized": "O aparelho está conectado mas NÃO autorizou este computador. Desbloqueie a tela do celular "
                    "e toque em 'Permitir' na janela 'Permitir depuração USB?' (marque 'Sempre permitir deste computador').",
    "offline": "O aparelho aparece como 'offline'. Desconecte e reconecte o cabo; se persistir, rode 'adb kill-server' "
               "e conecte de novo.",
    "multiple": "Há mais de um aparelho/emulador conectado. Defina ANDROID_SERIAL=<serial> (veja 'adb devices').",
    "nopermission": "Linux sem permissão de acesso ao USB: instale as regras udev (Debian/Ubuntu: "
                    "'sudo apt install android-sdk-platform-tools-common'), rode 'sudo usermod -aG plugdev $USER', "
                    "saia e entre de novo na sessão e reconecte o cabo.",
}


def ajuda(doc):
    """--help / -h em qualquer script: mostra a documentação e sai sem tocar no aparelho."""
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(doc)
        sys.exit(0)


def ler_texto(caminho):
    """Lê listas escritas em qualquer editor: UTF-8 (com ou sem BOM) ou UTF-16 (PowerShell 5.1)."""
    with open(caminho, "rb") as f:
        b = f.read()
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return b.decode("utf-16")
    return b.decode("utf-8-sig", "replace")


def caminho_local(p):
    """Caminho no computador. No Windows, aceita o formato do Git Bash (/e/Backup -> E:\\Backup),
    que o Python interpretaria como C:\\e\\Backup quando MSYS_NO_PATHCONV=1 está ligado."""
    if os.name == "nt":
        import re as _re
        m = _re.match(r"^/([a-zA-Z])(/.*)?$", p)
        if m:
            p = m.group(1).upper() + ":" + (m.group(2) or "/").replace("/", "\\")
    return os.path.abspath(p)


# Apps que nunca são removidos nem restringidos em lote: bancos, carteiras, governo, autenticação, empresa.
SENSIVEL = [
    ("financeiro", r"bank|banco|bradesco|itau|santander|caixa|nubank|nu\.production|intermedium|bancointer|c6bank|"
                   r"picpay|mercadopago|pagseguro|pagbank|(^|\.)bb(\.|$)|br\.com\.bb|neon|sicredi|sicoob|banrisul|"
                   r"safra|btg|br\.com\.xp|willbank|digio|paypal|wise|revolut|bancopan|bancooriginal|cielo|getnet|"
                   r"cartao|credit|card|fgts|serasa|boleto|pix"),
    ("cripto/carteira", r"wallet|crypto|binance|coinbase|exodus|trustapp|metamask|bitcoin|btc|ledger|atomic|okx|"
                        r"bybit|kucoin|mercadobitcoin|foxbit|novadax|coin"),
    ("governo", r"(^|\.)gov(\.|$)|govbr|receita|detran|inss|meuinss|conectesus|cnh|esocial|ctps|carteiradigital|"
                r"registrocivil|etitulo|(^|\.)tse(\.|$)|serpro|denatran|caixatem"),
    ("autenticação/segurança", r"authenticator|authy|2fa|otp|token|keepass|bitwarden|1password|lastpass|vpn|"
                               r"antivirus|security|avast|kaspersky|norton|mcafee"),
    ("empresa/MDM", r"intune|companyportal|airwatch|workspace|mdm|knox"),
]


def categoria_sensivel(pacote):
    import re as _re
    pl = pacote.lower()
    for cat, rx in SENSIVEL:
        if _re.search(rx, pl):
            return cat
    return ""


def require_device():
    need_adb()
    s = state()
    if s != "device":
        print(f"ERRO: estado do aparelho = '{s}'.\n{GUIA_ESTADO.get(s, '')}", file=sys.stderr)
        sys.exit(2)


def device_now():
    """Hora atual do aparelho em segundos Unix (para filtros por idade dos arquivos)."""
    try:
        return int(sh("date +%s", timeout=20).strip())
    except ValueError:
        return int(time.time())


def q(s):
    """Aspas simples seguras para o shell do aparelho."""
    return "'" + s.replace("'", "'\"'\"'") + "'"   # fecha aspas, insere ' entre aspas duplas, reabre
