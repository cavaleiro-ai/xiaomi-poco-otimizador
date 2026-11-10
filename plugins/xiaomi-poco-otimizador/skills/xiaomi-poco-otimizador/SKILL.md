---
name: xiaomi-poco-otimizador
description: Diagnóstico profundo, otimização e limpeza segura de celulares Android pelo computador, via ADB e cabo USB, com foco em Xiaomi, POCO e Redmi (HyperOS/MIUI) e suporte a Samsung, Motorola, Pixel e outros. Investiga obsolescência programada, limitação térmica de CPU, brilho e carga, saúde da bateria e do armazenamento, RAM saturada, apps mineradores ou espiões e apps sem uso, e gera relatório. Remove bloatware de forma reversível, restringe apps em segundo plano e faz backup verificado de fotos, vídeos e WhatsApp no PC ou HD externo antes de liberar espaço. Estuda a câmera e avalia overclock. Use quando a pessoa quiser deixar o celular mais rápido, entender por que ele está lento, esquentando ou descarregando, tirar apps de fábrica (debloat), liberar espaço, fazer backup pelo computador, analisar um Android com adb ou investigar obsolescência programada, mesmo sem dizer "ADB". Also for English requests to speed up, debloat, diagnose or back up an Android phone over adb.
---

# Xiaomi POCO Otimizador

Raio-x, otimização e limpeza segura de um celular Android conectado ao computador por ADB.
A pessoa do outro lado normalmente não é técnica: ela quer o celular mais rápido, com mais espaço,
e quer entender o que está acontecendo. O trabalho tem duas metades. Uma é investigar com rigor e
explicar em linguagem simples. A outra é alterar o aparelho só com autorização, sempre de forma
reversível e sem perder nada.

Responda no idioma da pessoa (padrão: português do Brasil).

## Como chamar os scripts

- Os scripts ficam em `scripts/`, dentro da pasta desta skill. O caminho completo aparece como
  "Base directory" quando a skill é carregada. Nos exemplos abaixo, **`<SK>` é esse caminho**:
  substitua-o pelo caminho real, entre aspas, em cada comando. Variáveis de shell não passam de um
  comando para o outro.
- Rode tudo **a partir da pasta de trabalho** (próxima seção), nunca a partir da pasta da skill. Assim
  os dados pessoais ficam com a pessoa e não no cache de plugins.
- Python: use `python` no Windows (se abrir a Microsoft Store ou falhar, use `py`) e `python3` no macOS
  e no Linux. Só a biblioteca padrão é usada. Todo script aceita `--help`, que não toca no aparelho.
- **Windows com Git Bash:** prefixe cada comando com `MSYS_NO_PATHCONV=1`. Sem isso, `/sdcard/DCIM`
  vira `C:/Program Files/Git/sdcard/DCIM`. Use caminhos do computador no formato `E:\Backup` ou
  `E:/Backup`. Os scripts também aceitam `/e/Backup`, mas outros comandos não.
- **Windows com PowerShell** (quando o Git não está instalado): não use o prefixo, que só existe no
  Bash. Rode `python "<SK>\scripts\nome.py" ...` direto; caminhos como `/sdcard/DCIM` passam sem
  conversão. No Windows PowerShell 5.1, encadeie comandos com `;`, porque `&&` não existe.
- **Comandos longos:** o diagnóstico rápido pode passar de 2 minutos; dê um timeout de 5 minutos.
  Coleta completa, bugreport, backup e cópia de APKs levam de minutos a horas: rode em segundo plano,
  acompanhe por `_coleta.log` ou `_logs/progresso.txt` e dê uma estimativa de tempo à pessoa.

Exemplo no Git Bash:
```
cd "C:/Users/ana/celular_poco_2026-11-08" && MSYS_NO_PATHCONV=1 python "<SK>/scripts/saude_rapida.py" --saida analise/diagnostico_rapido.md
```

## Princípios (leia antes do primeiro comando)

1. **Primeiro só leitura.** Diagnóstico e varredura não alteram nada no aparelho. Comece por eles
   mesmo quando a pessoa pedir "otimize", porque o plano depende do que for encontrado e ela precisa
   ver o plano antes de autorizar.
2. **Autorização explícita por fase.** Remover apps, restringir apps, limpar caches, mudar
   configurações e apagar arquivos exigem que a pessoa aprove aquela fase, com as palavras dela, depois
   de ver o que será feito: lista, quantidade e espaço.
   - "Analise meu celular" não autoriza mudanças.
   - "Implemente as melhorias" autoriza só o plano apresentado.
   - Apagar mídia exige uma aprovação própria, dada depois de a pessoa ver a tabela de exclusão. Isso
     vale mesmo que o pedido original já diga "libere espaço".
   - Registre a frase da autorização no log de execução.
   - Todos os scripts que alteram algo rodam em simulação até receberem `--aplicar`.
3. **Tudo reversível.** Apps saem com `pm uninstall -k --user 0` e os dados ficam no aparelho.
   - Apps de fábrica voltam com `cmd package install-existing`.
   - De apps instalados pela pessoa, o script copia o APK antes, porque o Android pode apagá-lo.
   - Cada script gera um arquivo RESTAURAR, que `restaurar.py` executa.
   - Nunca faça root, desbloqueio de bootloader, flash, wipe, reset de fábrica, `pm clear` (apaga dados
     de app) nem alterações em partições de sistema. Tudo isso é irreversível ou pode travar o
     aparelho, e nada disso é necessário para os ganhos que esta skill entrega.
4. **Nada é apagado sem cópia conferida.** Arquivo do usuário só sai do celular por
   `limpar_verificado.py`. Ele confere cada arquivo contra o backup (tamanho e data, ou MD5) e mantém
   os últimos N dias. Nunca use `adb shell rm` por conta própria. Nunca apague `WhatsApp/Databases`,
   `WhatsApp/Backups`, `Android/data` nem `Android/obb`. Avise antes que mídia apagada do WhatsApp
   continua aparecendo como miniatura na conversa, mas não abre mais no celular.
5. **Apps sensíveis só com confirmação item a item.** Bancos, carteiras de cripto, governo,
   autenticadores e apps da empresa às vezes ficam meses sem uso e fazem muita falta na hora que se
   precisa deles. `apps_sem_uso.py` marca esses apps e `restringir_segundo_plano.py` os pula. Nunca os
   remova nem os restrinja em lote.
6. **Privacidade.** A coleta contém dados pessoais: lista de apps, logs e estatísticas de uso. Ela fica
   no computador da pessoa. Não envie nada a serviços externos. Antes de qualquer publicação, como
   relatório no GitHub ou em fórum, remova serial, IMEI, contas e nomes.
7. **Honestidade sobre os achados.** Separe fato medido, inferência e hipótese. Limitação térmica
   agressiva, bateria gasta e armazenamento cheio são achados reais e devem ser descritos com números.
   Só chame algo de "obsolescência programada" se houver evidência de degradação proposital: código ou
   configuração que reduz desempenho por idade, data, número de ciclos ou versão, sem motivo técnico,
   ou tratamento diferente para apps e benchmarks. Os critérios estão em `references/diagnostico.md`.
   Não exagere nem minimize.

## Preparação

- **Pasta de trabalho no computador:** crie uma, por exemplo `~/celular_<modelo>_<AAAA-MM-DD>/`, com
  as subpastas `coleta/`, `analise/` e `execucao/`. Logs, relatórios e arquivos RESTAURAR ficam ali.
- **Fase 0, conexão:** sempre comece por `python "<SK>/scripts/verificar_conexao.py"`. Ele confere o
  adb, a autorização e a identidade do aparelho, e diz se é Xiaomi. Se falhar, passe à pessoa só os
  passos que faltam, numerados e em linguagem simples, tirados de `references/conexao_adb.md`. Inclua
  os passos da marca dela. Ela faz esses passos na tela do celular, porque você não consegue tocar nele.

## Qual fase usar

| A pessoa diz... | Faça |
|---|---|
| "está lento", "esquenta", "bateria acaba rápido" | Fase 1. Se houver sinais fortes, ofereça a Fase 2 |
| "investigue obsolescência programada", "varredura completa", "relatório" | Fases 1 e 2 |
| "deixe mais rápido", "tire os apps de fábrica" | Fases 1 e 2 (completa em Xiaomi, por causa da análise térmica; `--rapido` nos demais), Fase 3, autorização e Fase 4 |
| "libere espaço", "faça backup das fotos/WhatsApp" | Fase 5 |
| "melhore a câmera", "dá para fazer overclock?" | Seção "Overclock e câmera" |

## Fase 1: diagnóstico rápido (somente leitura, 1 a 3 min)

```
python "<SK>/scripts/saude_rapida.py" --saida analise/diagnostico_rapido.md
```
Explique o resultado em até 10 linhas, do problema mais grave ao menos grave. Para cada ponto, diga o
que significa na prática: "o armazenamento está 93 % cheio; isso deixa tudo mais lento" vale mais do
que "/data 93 %". Os limiares e o significado de cada número estão em `references/diagnostico.md`.

## Fase 2: varredura profunda e relatório (somente leitura)

1. **Coleta.**
   - Completa: `python "<SK>/scripts/coletar.py" coleta`. Inclui bugreport e leva de 20 a 60 minutos.
   - Rápida: some `--rapido`. Leva de 3 a 8 minutos e não gera bugreport, sem o qual não há análise
     térmica da Xiaomi nem saúde do armazenamento.
2. **Análises específicas:**
   - Xiaomi/POCO/Redmi, só com a coleta completa:
     `python "<SK>/scripts/analisar_termico_xiaomi.py" coleta/10_bugreport analise/termico.md`. Ele
     reconstrói em que temperatura cada limite de CPU, GPU, brilho e carga é aplicado e quanto tempo o
     aparelho passou limitado. Leia `references/xiaomi_hyperos.md`.
   - Apps parados: `python "<SK>/scripts/apps_sem_uso.py" --coleta coleta --saida analise/apps_sem_uso.md`.
     Some `--incluir-sistema` para candidatos a debloat.
   - Mineradores e espiões: `python "<SK>/scripts/analisar_apks.py" --puxar analise/apks --saida analise/apks.md`.
     Ele copia e analisa os apps instalados fora de lojas oficiais. Um veredito ALTO é forte indício de
     mineração: confirme com a pessoa se ela conhece o app.
   - Câmera, se for assunto:
     `python "<SK>/scripts/resumo_camera.py" --arquivo coleta/03_dumpsys/zz_media_camera.txt --saida analise/camera.md`.
3. **Leitura dirigida.** Use grep na coleta para responder às perguntas do pedido. O mapa "pergunta →
   arquivo" e os critérios de obsolescência estão em `references/diagnostico.md`. Nunca leia os
   arquivos inteiros: eles são enormes.
4. **Relatório.** Use o modelo de `references/modelos.md`: conclusões primeiro, depois evidências com
   arquivo de origem. Classifique cada achado como fato, inferência ou hipótese e termine com o que a
   pessoa pode fazer. Salve como `RELATORIO_<modelo>_<data>.md` na pasta de trabalho.

## Fase 3: plano de otimização

Monte o plano a partir dos achados, não de uma lista genérica. Para cada item, diga o ganho esperado,
o risco e como desfazer. O plano tem estes blocos:
- **Ajustes manuais** que só a pessoa faz na tela: reiniciar, modo de desempenho, taxa de atualização,
  extensão de memória, carregador original.
- **Debloat em níveis:**
  - Nível 1: anúncios, telemetria e duplicados. Seguro.
  - Nível 2: perde uma função que talvez não use.
  - Nível 3: nunca remover.
  - Use as listas de `references/xiaomi_hyperos.md` ou `references/outras_marcas.md` e explique cada
    pacote numa frase. Para pacotes que não estão nas listas, pesquise o que fazem antes de sugerir. Na
    dúvida, deixe fora.
- **Apps pesados em segundo plano** (consumo de bateria e RAM medido na coleta) para restringir.
  Mensagens, bancos e autenticadores ficam fora.
- **Limpeza de caches** (`pm trim-caches`). Apaga só arquivos temporários de apps, inclusive mídia em
  cache do Telegram e de redes sociais, que volta a ser baixada quando necessário. Não tem como
  desfazer, mas não apaga dados, conversas nem arquivos da pessoa.
- **Animações em 0,5x** pelo ADB, quando permitido, ou pela tela.
- **Espaço:** quanto a Fase 5 liberaria. Ela tem autorização separada.

Termine pedindo a autorização com uma pergunta objetiva, por exemplo: "Posso aplicar o nível 1,
restringir estes 8 apps, limpar os caches e ajustar as animações?". Se a pessoa aprovar só parte, faça
só essa parte.

## Fase 4: aplicar (só o que foi autorizado)

1. **Retrato do antes:** `pm list packages --user 0`, `df -h /data` e `/proc/meminfo`, em `execucao/`.
2. **Remoção:** escreva os pacotes aprovados em `execucao/nivel1.txt`, um por linha.
   - Simule: `python "<SK>/scripts/remover_pacotes.py" --lista execucao/nivel1.txt`.
   - Confira a saída e aplique: repita com `--aplicar --registro execucao`.
   - Os APKs de apps instalados pela pessoa são copiados para `execucao/apks/`.
   - O script recusa sozinho pacotes essenciais, o launcher, o teclado e o WebView em uso.
   - Aplique o nível 2 de preferência depois de a pessoa usar o celular um dia com o nível 1.
3. **Restrição:**
   - Simule: `python "<SK>/scripts/restringir_segundo_plano.py" <pacotes>`.
   - Aplique: repita com `--aplicar --registro execucao`. Some `--doze` para tirar o app da isenção de
     economia de bateria.
4. **Caches, se autorizados:** `adb shell pm trim-caches 999G`.
5. **Animações, se autorizadas:**
   - Rode `verificar_conexao.py --testar-escrita`.
   - Se for permitido, leia os valores atuais de `window_animation_scale`,
     `transition_animation_scale` e `animator_duration_scale` com `adb shell settings get global <nome>`.
     Um valor `null` equivale a 1.0.
   - Grave em `execucao/RESTAURAR_animacoes.txt` uma linha por chave, no formato
     `adb shell settings put global <nome> <valor antigo>`.
   - Só então aplique `adb shell settings put global <nome> 0.5` nas três chaves.
   - Se a escrita for bloqueada, comum na Xiaomi, passe o caminho na tela (Opções do desenvolvedor).
6. **Retrato do depois** e registro em `execucao/EXECUCAO_<data>.md`: o que foi feito, números de antes
   e depois, arquivos RESTAURAR e passos manuais pendentes. Recomende reiniciar.

## Fase 5: backup e liberação de espaço

1. **Combine com a pessoa:**
   - o destino do backup, por exemplo um HD externo;
   - as pastas (`--padrao` cobre câmera, Pictures, Movies, Download, Documents, música, gravações,
     WhatsApp, WhatsApp Business e Telegram, inclusive as pastas antigas do Android 8 a 10);
   - quantos dias recentes ficam no celular (padrão 30).
   - A ROM baixada pela atualização (`/sdcard/Download/downloaded_rom`) entra no backup do Download.
     Para liberá-la, passe-a como origem própria na limpeza com `--dias 0`. Se a pessoa preferir não
     guardar cópia, ela mesma apaga o arquivo pelo app Arquivos.
2. **Planeje:** `python "<SK>/scripts/backup_midias.py" --destino "E:\Backup celular" --padrao --listar`
   mostra o tamanho e o que falta copiar. Confira se cabe e se o disco não é FAT32, que não aceita
   arquivos de 4 GB ou mais.
3. **Copie:** repita sem `--listar` (ou use `--origem <pasta>`, que pode ser repetido) e rode em segundo
   plano. Só siga quando o resumo mostrar "falhas de cópia: 0".
   - O script pode ser interrompido e retomado.
   - Arquivos criados durante a cópia entram na execução seguinte.
   - Nomes que o Windows não aceita ficam só no celular e aparecem no relatório.
4. **Mostre o plano de exclusão:** para cada pasta que a pessoa quer limpar, rode
   `python "<SK>/scripts/limpar_verificado.py" --destino "E:\Backup celular" --origem /sdcard/DCIM --origem "/sdcard/Android/media/com.whatsapp/WhatsApp/Media" --dias 30`,
   sem `--aplicar`. Mostre a tabela, repita o aviso do WhatsApp e pergunte se pode apagar.
5. **Apague, só após esse "sim":** repita com `--aplicar`. Se o backup não foi feito pelo
   `backup_midias.py` (as datas não batem), use `--hash`, que confere o conteúdo e é bem mais lento.
   Informe o espaço livre antes e depois.

## Fase 6: fechamento

Entregue um resumo curto:
- o que mudou, com os números de antes e depois;
- onde estão o relatório, os backups e os arquivos RESTAURAR;
- como desfazer cada coisa, com `python "<SK>/scripts/restaurar.py" <arquivo RESTAURAR>`;
- os passos manuais que faltam.

Por segurança, recomende desligar a Depuração USB ao terminar.

## Overclock e câmera: o que é realista

- **Overclock:** sem root, não existe. As frequências máximas vêm do kernel e do firmware. O que dá para
  recuperar é o desempenho que a política térmica corta: aparelho frio, sem capa ao jogar, sem jogar
  carregando, modo de desempenho ligado, armazenamento e RAM folgados. Com root e kernel modificado
  existem riscos reais (instabilidade, aquecimento, perda de garantia e de apps de banco), e esta skill
  não faz isso. Mostre `cpuinfo_max_freq` contra `scaling_max_freq` para provar o ponto.
- **Câmera:** rode `resumo_camera.py` e leia `references/camera.md`. Normalmente o ganho real vem de
  três coisas: configurações do app nativo (modo de alta resolução, 4K, estabilização, HDR), um app
  Camera2 compatível quando o nível for FULL ou LEVEL_3, e menos aquecimento e mais espaço livre. Seja
  claro sobre o que não muda: sensor, OIS e câmeras escondidas sem root.

## Problemas comuns

| Sintoma | Causa provável e solução |
|---|---|
| `unauthorized` | A pessoa precisa tocar em "Permitir" na janela de depuração USB do celular, com a tela desbloqueada |
| Nenhum aparelho em `adb devices` | Cabo só de carga, modo USB errado ou driver (Windows); ver `references/conexao_adb.md` |
| `no permissions` (Linux) | Regras udev; o `verificar_conexao.py` mostra os comandos |
| `SecurityException: WRITE_SECURE_SETTINGS` | Xiaomi sem "Depuração USB (configurações de segurança)": fazer o ajuste pela tela |
| `INJECT_EVENTS` negado | Mesmo motivo; não dá para simular toques; passe os passos para a pessoa |
| `Failure [-1000]` ao remover | O fabricante bloqueia a remoção; o script desativa o pacote (`pm disable-user`), também reversível |
| `adb pull` de pasta aborta no meio | Normal em pastas grandes; use `backup_midias.py` (lotes por tar, conferência e recópia) |
| `/sdcard/...` vira `C:/Program Files/Git/...` | Git Bash; prefixe o comando com `MSYS_NO_PATHCONV=1` |
| Script parece parado | Coletas e cópias grandes são lentas; veja `_coleta.log` ou `_logs/progresso.txt` |

## Referências (leia conforme a necessidade)

- `references/conexao_adb.md`: passo a passo para a pessoa ligar a depuração USB (por marca),
  instalar o ADB e resolver problemas de conexão.
- `references/diagnostico.md`: limiares e interpretação de cada indicador, onde procurar cada coisa na
  coleta, critérios de obsolescência programada e overclock.
- `references/xiaomi_hyperos.md`: mi_thermald, Joyose, PowerKeeper, restrições do ADB na Xiaomi,
  menus ocultos e listas de debloat por nível.
- `references/outras_marcas.md`: Samsung, Motorola, Pixel, Oppo/Realme/OnePlus e regras gerais de
  debloat.
- `references/camera.md`: como estudar a câmera e o que dá para melhorar.
- `references/modelos.md`: modelos de relatório, plano e registro de execução.

## Scripts

| Script | O que faz | Altera o celular? |
|---|---|---|
| `verificar_conexao.py` | Confere adb, autorização e identidade | Não. Com `--testar-escrita`, regrava o valor atual de uma configuração |
| `saude_rapida.py` | Diagnóstico rápido com pontos de atenção | Não |
| `coletar.py` | Varredura completa (`--rapido`, `--sem-bugreport`) | Não |
| `analisar_termico_xiaomi.py` | Política térmica real a partir do bugreport (Xiaomi) | Não (lê arquivo) |
| `apps_sem_uso.py` | Apps sem uso há N dias, com marcação de sensíveis | Não |
| `analisar_apks.py` | Mineradores, permissões de risco, assinatura de depuração, servidores | Não (copia APKs) |
| `resumo_camera.py` | Câmeras, níveis Camera2, câmeras escondidas, perfis de vídeo | Não |
| `remover_pacotes.py` | Remoção reversível com lista de protegidos e RESTAURAR | Só com `--aplicar` |
| `restringir_segundo_plano.py` | Restringe o segundo plano e grava o modo anterior | Só com `--aplicar` |
| `restaurar.py` | Executa um arquivo RESTAURAR (só comandos de desfazer) | Sim (desfaz) |
| `backup_midias.py` | Backup verificado e retomável para PC ou HD externo | Não (só copia) |
| `limpar_verificado.py` | Apaga só o que tem cópia conferida; mantém os últimos N dias | Só com `--aplicar` |
