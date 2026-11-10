# -*- coding: utf-8 -*-
"""Backup VERIFICADO das mídias do celular para o computador ou HD externo. Não apaga nada no celular.

Uso:
  python backup_midias.py --destino "D:\\Backup celular" --padrao [--listar]
  python backup_midias.py --destino "D:\\Backup celular" --origem /sdcard/DCIM [--origem "/sdcard/Android/media/com.whatsapp/WhatsApp/Media"]

  --padrao           DCIM, Pictures, Movies, Download, Documents, Music, gravações, mídia do WhatsApp/WhatsApp Business
                     e Telegram (só as pastas que existirem)
  --origem PASTA     pasta do celular (pode repetir)
  --listar           só mostra quantos arquivos e GB existem e quanto falta copiar (nada é copiado)
  --incluir-ocultos  inclui miniaturas (.thumbnails), status do WhatsApp (.Statuses) e lixeira (.trashed-*)

Como funciona: copia em lotes por um fluxo 'tar' (muito mais estável que 'adb pull' de pastas inteiras,
que costuma abortar no meio em pastas grandes), confere CADA arquivo pelo tamanho, recopia individualmente
o que falhar e pode ser interrompido e retomado: o que já está igual no destino é pulado.
Estrutura no destino: espelho do celular. /sdcard/DCIM/Camera/x.jpg -> <destino>/DCIM/Camera/x.jpg
Registros em <destino>/_logs/.
"""
import datetime
import os
import posixpath
import shutil
import subprocess
import sys
import tarfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _adb  # noqa: E402
import _midias as M  # noqa: E402

_adb.utf8_stdout()
_adb.ajuda(__doc__)
argv = sys.argv[1:]


def valores(nome):
    return [argv[i + 1] for i, a in enumerate(argv) if a == nome and i + 1 < len(argv)]


if not valores("--destino"):
    print(__doc__)
    sys.exit(1)
DEST = _adb.caminho_local(valores("--destino")[0])
LISTAR = "--listar" in argv
OCULTOS = "--incluir-ocultos" in argv
PADRAO = ["/sdcard/DCIM", "/sdcard/Pictures", "/sdcard/Movies", "/sdcard/Download", "/sdcard/Documents",
          "/sdcard/Music", "/sdcard/Recordings", "/sdcard/MIUI/sound_recorder", "/sdcard/Android/media/com.whatsapp/WhatsApp/Media",
          "/sdcard/Android/media/com.whatsapp.w4b/WhatsApp Business/Media",
          "/sdcard/WhatsApp/Media", "/sdcard/WhatsApp Business/Media",   # WhatsApp no Android 8–10
          "/sdcard/Telegram",
          "/sdcard/Android/media/org.telegram.messenger/Telegram"]
_adb.require_device()
origens = [M.normalizar(o) for o in valores("--origem")]
if "--padrao" in argv:
    for o in PADRAO:
        if _adb.sh(f"[ -d {_adb.q(o)} ] && echo sim", timeout=20).strip() == "sim":
            origens.append(o)
origens = list(dict.fromkeys(origens))
if not origens:
    sys.exit("Nenhuma pasta de origem encontrada. Use --origem /sdcard/... ou --padrao.")
for o in origens:
    M.relativo(o + "/x")  # recusa caminhos fora do armazenamento interno

os.makedirs(os.path.join(DEST, "_logs"), exist_ok=True)
CARIMBO = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
LOG = open(os.path.join(DEST, "_logs", f"backup_{CARIMBO}.log"), "a", encoding="utf-8")
PROG = os.path.join(DEST, "_logs", "progresso.txt")


def log(msg):
    linha = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(linha, flush=True)
    LOG.write(linha + "\n")
    LOG.flush()


def progresso(msg):
    with open(PROG, "w", encoding="utf-8") as f:
        f.write(msg + "\n")


FS = M.sistema_arquivos(DEST)
TEM_TAR = _adb.sh("command -v tar", timeout=20).strip().endswith("/tar")
log(f"=== backup {'(só listagem)' if LISTAR else ''} -> {DEST} (sistema de arquivos: {FS or '?'}; tar no aparelho: "
    f"{'sim' if TEM_TAR else 'não'}) ===")

# ---------- levantamento ----------
inventario, faltam, nao_copiaveis = {}, {}, []
for o in origens:
    itens = M.listar(o, OCULTOS)
    inventario[o] = itens
    falta = {}
    dup = M.colisoes_maiusculas(itens)
    for p, (s, mt) in itens.items():
        rel = M.relativo(p)
        if p in dup:
            nao_copiaveis.append((p, "outro arquivo na mesma pasta tem o mesmo nome com maiúsculas/minúsculas diferentes"))
            continue
        if os.name == "nt" and M.invalido_windows(rel):
            nao_copiaveis.append((p, "nome inválido no Windows"))
            continue
        if FS.upper().startswith("FAT") and s >= 4 * 1024 ** 3:
            nao_copiaveis.append((p, "arquivo de 4 GB ou mais num disco FAT32 (formate em exFAT ou NTFS)"))
            continue
        if not M.igual(M.local(DEST, p), s, mt):
            falta[p] = (s, mt)
    faltam[o] = falta
    log(f"{o}: {len(itens)} arquivos, {M.fmt_gb(sum(s for s, _ in itens.values()))}; falta copiar {len(falta)} "
        f"({M.fmt_gb(sum(s for s, _ in falta.values()))})")
total_falta = sum(s for f in faltam.values() for s, _ in f.values())
if nao_copiaveis:
    log(f"{len(nao_copiaveis)} arquivo(s) não podem ser copiados para este destino e ficarão só no celular (ver relatório).")
livre = shutil.disk_usage(DEST).free
log(f"Total a copiar: {M.fmt_gb(total_falta)}; livre no destino: {M.fmt_gb(livre)}")
if LISTAR:
    sys.exit(0)
if total_falta + 1e9 > livre:
    sys.exit("Espaço insuficiente no destino. Libere espaço ou escolha outro disco.")


# ---------- cópia ----------
def tar_lote(pasta_dev, nomes, pasta_local):
    """Copia um lote por 'tar' em fluxo. Devolve quantos arquivos foram gravados."""
    cmd = f"cd {_adb.q(pasta_dev)} && tar cf - " + " ".join(_adb.q("./" + n) for n in nomes)
    proc = subprocess.Popen(_adb.ADB + ["exec-out", cmd], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    gravados, tmp = 0, None
    try:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tf:
            for m in tf:
                if not m.isfile():
                    continue
                nome = m.name[2:] if m.name.startswith("./") else m.name
                if nome.startswith("/") or ".." in nome.split("/"):
                    continue
                dst = os.path.join(pasta_local, *nome.split("/"))
                if os.name == "nt" and len(dst) >= 240 and not dst.startswith("\\\\?\\"):
                    dst = "\\\\?\\" + os.path.abspath(dst)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                tmp = dst + ".parcial"
                with open(tmp, "wb") as out:
                    shutil.copyfileobj(tf.extractfile(m), out, 1 << 20)
                os.replace(tmp, dst)
                tmp = None
                os.utime(dst, (m.mtime, m.mtime))
                gravados += 1
    except (tarfile.TarError, OSError, EOFError) as e:
        log(f"   lote não transferido em {pasta_dev} ({type(e).__name__}); será dividido ou copiado arquivo a arquivo")
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)
        try:
            proc.stdout.close()
            proc.wait(timeout=60)
        except Exception:
            proc.kill()
    return gravados


def pull(p, s):
    dst = M.local(DEST, p)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    # baixa para um caminho curto e só então move: o adb.exe não lida bem com caminhos longos ou acentuados
    tmp = os.path.join(DEST, "_logs", "baixando.parcial")
    for _ in range(4):
        _adb.adb("pull", "-a", p, tmp, timeout=7200)
        if M.tamanho_local(tmp) == s:
            os.replace(tmp, dst)
            return True
        _adb.adb("wait-for-device", timeout=120)
        time.sleep(2)
    if os.path.exists(tmp):
        os.remove(tmp)
    return False


t0, copiado, falhas = time.time(), 0, []
LIM_CMD, LIM_N, LIM_B = 60000, 400, 1.5e9
for o in origens:
    falta = faltam[o]
    if not falta:
        continue
    por_pasta = {}
    for p in sorted(falta):
        por_pasta.setdefault(posixpath.dirname(p), []).append(p)
    lotes = []
    for pasta, arqs in por_pasta.items():
        atual, tam, comp = [], 0, 0
        for p in arqs:
            n = posixpath.basename(p)
            s = falta[p][0]
            if atual and (len(atual) >= LIM_N or tam + s > LIM_B or comp + len(n) + 6 > LIM_CMD):
                lotes.append((pasta, atual))
                atual, tam, comp = [], 0, 0
            atual.append(p)
            tam += s
            comp += len(n) + 6
        if atual:
            lotes.append((pasta, atual))
    for i, (pasta, arqs) in enumerate(lotes, 1):
        if TEM_TAR:
            # lote adaptativo: alguns aparelhos/versões do adb limitam o tamanho do comando (4 a 8 KB em
            # aparelhos antigos). Se o lote não trouxer nada, divide ao meio e reduz o limite dos próximos.
            pilha = [arqs]
            while pilha:
                sub = pilha.pop()
                nomes = [posixpath.basename(p) for p in sub]
                if len(sub) > 1 and sum(len(x) + 6 for x in nomes) > LIM_CMD:
                    meio = len(sub) // 2
                    pilha += [sub[meio:], sub[:meio]]
                    continue
                n = tar_lote(pasta, nomes, os.path.dirname(M.local(DEST, sub[0])))
                if n == 0 and len(sub) > 1:
                    LIM_CMD = max(1500, min(LIM_CMD, sum(len(x) + 6 for x in nomes) // 2))
                    meio = len(sub) // 2
                    pilha += [sub[meio:], sub[:meio]]
        restantes = [p for p in arqs if not M.igual(M.local(DEST, p), *falta[p])]
        for p in restantes:   # o que o tar não trouxe: arquivo a arquivo
            if not pull(p, falta[p][0]):
                falhas.append(p)
                log(f"   FALHOU: {p}")
        copiado += sum(falta[p][0] for p in arqs if p not in falhas)
        dt = max(time.time() - t0, 1)
        vel = copiado / dt
        eta = (total_falta - copiado) / vel / 60 if vel else 0
        msg = (f"{o} | lote {i}/{len(lotes)} | {M.fmt_gb(copiado)} de {M.fmt_gb(total_falta)} "
               f"({100 * copiado / max(total_falta, 1):.0f} %) | {vel / 1e6:.0f} MB/s | faltam ~{eta:.0f} min | falhas {len(falhas)}")
        progresso(msg)
        if i % 5 == 0 or i == len(lotes):
            log(msg)

# ---------- conferência final ----------
# Só conta como falha o que estava no levantamento inicial e continua no celular. Arquivos criados durante
# a cópia (fotos novas, mensagens chegando) entram na próxima execução e não travam a conclusão.
log("Conferência final (nova listagem do celular)...")
resumo, faltando, novos = [], [], 0
invalidos = {p for p, _ in nao_copiaveis}
with open(os.path.join(DEST, "_logs", f"manifesto_{CARIMBO}.tsv"), "w", encoding="utf-8") as man:
    man.write("caminho_no_celular\ttamanho\tmtime\tcopia_ok\n")
    for o in origens:
        itens = M.listar(o, OCULTOS)
        ok = 0
        inicial = inventario[o]
        for p, (s, mt) in sorted(itens.items()):
            igual = M.igual(M.local(DEST, p), s, mt)
            ok += igual
            if not igual and p not in invalidos:
                if p in inicial and inicial[p] == (s, mt):
                    faltando.append(p)
                else:
                    novos += 1
            man.write(f"{p}\t{s}\t{mt}\t{'sim' if igual else 'nao'}\n")
        resumo.append((o, len(itens), sum(s for s, _ in itens.values()), ok))
with open(os.path.join(DEST, "_logs", f"nao_copiados_{CARIMBO}.txt"), "w", encoding="utf-8") as f:
    for p, motivo in nao_copiaveis:
        f.write(f"{p}\t{motivo}\n")
    for p in faltando:
        f.write(f"{p}\tfalha de cópia (rode o backup de novo para tentar outra vez)\n")
log("=== RESUMO ===")
for o, n, b, ok in resumo:
    log(f"{o}: {n} arquivos ({M.fmt_gb(b)}), com cópia idêntica: {ok}")
log(f"Não copiáveis para este destino: {len(nao_copiaveis)}; falhas de cópia: {len(faltando)}; "
    f"arquivos novos ou alterados durante a cópia (entram na próxima execução): {novos}")
progresso(f"CONCLUÍDO | falhas {len(faltando)} | não copiáveis {len(nao_copiaveis)}")
sys.exit(0 if not faltando else 1)
