# -*- coding: utf-8 -*-
"""Funções compartilhadas por backup_midias.py e limpar_verificado.py.

Regra de caminhos (a mesma nos dois scripts, para a conferência ser exata):
  /sdcard/<caminho>  (ou /storage/emulated/0/<caminho>)  ->  <destino>/<caminho>
Ex.: /sdcard/DCIM/Camera/IMG_1.jpg  ->  D:\\Backup celular\\DCIM\\Camera\\IMG_1.jpg
"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _adb  # noqa: E402

RAIZES = ("/storage/emulated/0", "/storage/self/primary", "/mnt/sdcard", "/sdcard")
OCULTOS = re.compile(r"(^|/)(\.thumbnails|\.Statuses|\.trash|\.Trash|\.recycle|\.globalTrash)(/|$)|(^|/)\.trashed-\d+-")
RESERVADOS = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}


def normalizar(origem):
    o = origem.replace("\\", "/").rstrip("/")
    # Git Bash no Windows converte "/sdcard/X" em "C:/Program Files/Git/sdcard/X" ao chamar o Python.
    # Desfaz essa conversão (para evitar, exporte MSYS_NO_PATHCONV=1 antes de rodar os scripts).
    m = re.match(r"^[A-Za-z]:/.*?(/(?:sdcard|storage|mnt)(?:/.*)?)$", o)
    if m:
        o = m.group(1)
    for r in RAIZES:
        if o == r or o.startswith(r + "/"):
            return "/sdcard" + o[len(r):]
    return o


def relativo(caminho):
    c = normalizar(caminho)
    if not c.startswith("/sdcard/"):
        raise ValueError(f"fora do armazenamento interno: {caminho}")
    return c[len("/sdcard/"):]


def local(destino, caminho):
    p = os.path.join(destino, *relativo(caminho).split("/"))
    if os.name == "nt" and len(p) >= 240 and not p.startswith("\\\\?\\"):
        p = "\\\\?\\" + os.path.abspath(p)   # caminhos longos no Windows (limite clássico de 260 caracteres)
    return p


def igual(caminho_local, tamanho, mtime, tol=2):
    """Cópia conferida = mesmo tamanho E mesma data de modificação (tolerância de 2 s para FAT/exFAT e de
    1 h exata para mudança de horário de verão). O backup preserva a data, então a cópia feita por ele bate.
    Isso evita confundir dois arquivos diferentes que têm o mesmo caminho e o mesmo tamanho."""
    try:
        st = os.stat(caminho_local)
    except OSError:
        return False
    if st.st_size != tamanho:
        return False
    d = abs(st.st_mtime - mtime)
    return d <= tol or abs(d - 3600) <= tol


def colisoes_maiusculas(caminhos):
    """Caminhos que só diferem por maiúsculas/minúsculas: no Windows e no macOS virariam o MESMO arquivo."""
    if os.name != "nt" and sys.platform != "darwin":
        return set()
    vistos, dup = {}, set()
    for c in sorted(caminhos):
        k = c.lower()
        if k in vistos:
            dup.update({c, vistos[k]})
        else:
            vistos[k] = c
    return dup


def invalido_windows(rel):
    """Nomes que o Windows/NTFS/exFAT não aceita: ficam no celular e são listados no relatório."""
    for comp in rel.split("/"):
        if re.search(r'[<>:"\\|?*\x00-\x1f]', comp) or comp.endswith((".", " ")):
            return True
        if comp.split(".")[0].upper() in RESERVADOS:
            return True
    return False


def sistema_arquivos(destino):
    """Nome do sistema de arquivos do destino no Windows (NTFS, exFAT, FAT32...), ou '' se desconhecido."""
    if os.name != "nt":
        return ""
    try:
        import ctypes
        raiz = os.path.splitdrive(os.path.abspath(destino))[0] + "\\"
        buf = ctypes.create_unicode_buffer(64)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(ctypes.c_wchar_p(raiz), None, 0, None, None, None, buf, 64)
        return buf.value if ok else ""
    except Exception:
        return ""


def listar(origem, incluir_ocultos=False):
    """{caminho_no_aparelho: (tamanho, mtime)} de todos os arquivos sob 'origem'.
    Repete a listagem até a contagem bater com 'find | wc -l' (listagens grandes às vezes vêm incompletas)."""
    o = normalizar(origem)
    itens = {}
    for tentativa in range(4):
        out = _adb.sh(f"find {_adb.q(o)} -type f -print0 2>/dev/null | xargs -0 stat -c '%s|%Y|%n' 2>/dev/null",
                      timeout=3600, retries=2)
        itens = {}
        for ln in out.splitlines():
            p = ln.split("|", 2)
            if len(p) == 3 and p[0].isdigit() and p[1].lstrip("-").isdigit():
                itens[normalizar(p[2])] = (int(p[0]), int(p[1]))
        cnt = _adb.sh(f"find {_adb.q(o)} -type f 2>/dev/null | wc -l", timeout=1800).strip()
        if cnt.isdigit() and int(cnt) == len(itens):
            break
        time.sleep(2)
    if not incluir_ocultos:
        itens = {k: v for k, v in itens.items() if not OCULTOS.search(k)}
    return itens


def tamanho_local(p):
    try:
        return os.path.getsize(p)
    except OSError:
        return -1


def fmt_gb(b):
    return f"{b / 1e9:.2f} GB" if b >= 1e8 else f"{b / 1e6:.0f} MB"
