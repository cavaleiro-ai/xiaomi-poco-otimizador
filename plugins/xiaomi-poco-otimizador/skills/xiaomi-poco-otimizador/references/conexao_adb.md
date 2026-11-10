# Conectar o celular ao computador por ADB

Este arquivo tem os passos que a pessoa faz na tela do celular. Passe a ela só a parte necessária,
numerada, em linguagem simples e com os nomes de menu da marca dela. Os nomes variam um pouco entre
versões do sistema: se um menu não aparecer, peça para usar a busca das Configurações.

## 1. Instalar o ADB no computador

| Sistema | Comando ou caminho |
|---|---|
| Windows | `winget install Google.PlatformTools` no PowerShell, ou baixe o zip "SDK Platform-Tools for Windows" em https://developer.android.com/tools/releases/platform-tools e extraia em `C:\platform-tools` |
| macOS | `brew install android-platform-tools` |
| Debian/Ubuntu | `sudo apt install adb` |
| Fedora | `sudo dnf install android-tools` |

Os scripts procuram o adb no PATH e nas pastas mais comuns. Se estiver em outro lugar, defina a variável
`ADB` com o caminho completo.

## 2. Ligar as Opções do desenvolvedor

| Marca / sistema | Onde tocar 7 vezes | Onde ficam as Opções do desenvolvedor |
|---|---|---|
| Xiaomi, POCO, Redmi (HyperOS/MIUI) | Configurações → Sobre o telefone → **Versão do HyperOS** (ou **Versão do MIUI**) | Configurações → Configurações adicionais → Opções do desenvolvedor |
| Samsung (One UI) | Configurações → Sobre o telefone → Informações do software → **Número de compilação** | Configurações → Opções do desenvolvedor (no fim da lista) |
| Motorola, Google Pixel, Android puro | Configurações → Sobre o telefone → **Número da versão** | Configurações → Sistema → Opções do desenvolvedor |
| Oppo, Realme, OnePlus (ColorOS/realme UI/OxygenOS) | Configurações → Sobre o dispositivo → Versão → **Número da versão** | Configurações → Configurações adicionais (ou Sistema) → Opções do desenvolvedor |

O celular pode pedir o PIN de desbloqueio. Ao final aparece "Você agora é um desenvolvedor".

## 3. Ligar a Depuração USB

1. Em Opções do desenvolvedor, ligue **Depuração USB** e confirme.
2. **Só na Xiaomi/POCO/Redmi, opcional:** ligue também **Depuração USB (configurações de segurança)**.
   Ela exige conta Xiaomi conectada e chip SIM, às vezes com dados móveis ligados. Sem ela, o ADB lê
   tudo e remove apps, mas não altera configurações (como as animações) nem simula toques. Esses
   ajustes então são feitos pela tela. Ligue **Instalar via USB** se for preciso reinstalar um APK salvo.

## 4. Conectar

1. Use um cabo que transmita dados. Muitos cabos baratos só carregam. Prefira o cabo original e uma
   porta USB direta do computador, não um hub.
2. Desbloqueie o celular. Na notificação "Carregando via USB", escolha **Transferência de arquivos**.
3. Vai aparecer "Permitir depuração USB?" com a impressão digital RSA do computador. Marque **Sempre
   permitir deste computador** e toque em **Permitir**.
4. No computador, `adb devices` deve mostrar o serial com a palavra `device`.

## 5. Problemas de conexão

| O que aparece | O que fazer |
|---|---|
| Lista vazia | Troque o cabo ou a porta, confira o modo "Transferência de arquivos" e desligue e religue a Depuração USB. No Windows, instale o driver: "Google USB Driver" (Pixel, Xiaomi e a maioria), o "Samsung USB Driver" ou o driver do fabricante. Depois rode `adb kill-server` e `adb devices` |
| `unauthorized` | A janela de permissão não foi aceita. Desbloqueie a tela e procure a janela; se ela não aparecer, use Opções do desenvolvedor → **Revogar autorizações de depuração USB**, desconecte e conecte de novo |
| `offline` | Desconecte e reconecte; `adb kill-server`; reinicie o celular se persistir |
| `more than one device` | Defina `ANDROID_SERIAL=<serial>` (o serial aparece em `adb devices`) |
| Cai durante cópias longas | Desative a economia de energia USB do Windows ("Suspensão seletiva de USB"), use outra porta e mantenha o celular carregando |

## 6. Sem cabo: depuração por Wi-Fi (Android 11+)

1. Ligue o celular e o computador na mesma rede Wi-Fi.
2. No celular, abra Opções do desenvolvedor → **Depuração por Wi-Fi** → ligar → **Parear dispositivo
   com código**.
3. No computador, digite `adb pair IP:PORTA`, usando o IP e a porta do pareamento, e informe o código.
4. Depois digite `adb connect IP:PORTA`, usando o IP e a porta da tela principal da Depuração por Wi-Fi.

Cópias grandes ficam bem mais lentas que pelo cabo.

## 7. Ao terminar

Recomende desligar a Depuração USB, e na Xiaomi também a opção de configurações de segurança. Com ela
ligada, qualquer computador autorizado pode controlar o aparelho.

## Notas para o Claude (Windows)

- No Git Bash, exporte `MSYS_NO_PATHCONV=1` antes de comandos com caminhos do celular. Sem isso,
  `/sdcard/X` vira `C:/Program Files/Git/sdcard/X`.
- O `adb.exe` do Windows espera caminhos locais no formato `C:/...` ou `C:\...`, não `/c/...`.
  Use `cygpath -w` quando montar o caminho no Git Bash.
- Prefira escrever scripts com a ferramenta de arquivos em vez de heredocs longos no Bash: aspas e
  barras invertidas costumam ser alteradas.
