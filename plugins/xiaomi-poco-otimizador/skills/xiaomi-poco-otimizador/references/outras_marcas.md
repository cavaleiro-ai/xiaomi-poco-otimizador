# Outras marcas e regras gerais de debloat

## Regras gerais (valem para qualquer marca)

1. **Só remova o que sabe o que é.** Para um pacote desconhecido, pesquise o nome exato antes de
   sugerir. Uma boa referência é a lista do Universal Android Debloater Next Generation (UAD-ng), que
   classifica milhares de pacotes como Recommended, Advanced, Expert ou Unsafe:
   https://github.com/Universal-Debloater-Alliance/universal-android-debloater-next-generation
   Sugira só os "Recommended" e, com explicação, os "Advanced". Nunca sugira "Expert" ou "Unsafe".
2. **Nunca remova** o launcher, o teclado e o WebView em uso, nem o telefone/discador, SMS,
   Configurações, SystemUI, provedores (`com.android.providers.*`), Google Play Services e Play Store,
   o instalador de pacotes, o controlador de permissões, os componentes de rede e o gerenciador de
   bateria do fabricante. O `remover_pacotes.py` recusa todos esses e detecta os que estão em uso.
3. **Remova em poucos passos.** Remova um nível, peça para a pessoa usar o celular um dia e só então
   siga para o próximo. Se algo falhar, restaure o último lote com `restaurar.py`.
4. **Apps da operadora** (Claro, Vivo, TIM etc.) e instaladores de parceiros (Facebook, Amazon,
   Netflix pré-instalado, LinkedIn, Booking) costumam ser seguros de remover.

## Samsung (One UI)

**Caso documentado de limitação seletiva:** em 2022, testes independentes mostraram que o Game
Optimizing Service (`com.samsung.android.game.gos`) limitava o desempenho de milhares de jogos e apps
populares, mas não o de benchmarks. A Geekbench retirou vários modelos Galaxy do seu ranking. A
Samsung lançou uma atualização que permite escolher o modo de desempenho dos jogos no Game Booster.
O que fazer:
- Não remova o GOS pelo ADB: isso quebra o Game Launcher e o Game Booster.
- Use a opção de desempenho do Game Booster, que fica no menu de laboratório ou de "gerenciamento
  alternativo de desempenho" e muda de nome entre versões.

**Ajustes na tela:**
- **Proteção da bateria:** Configurações → Bateria (ou "Assistência do aparelho e bateria") → Proteger
  bateria. Limita a carga em torno de 85 % e reduz o desgaste.
- **Saúde da bateria:** app Samsung Members → Suporte → Diagnóstico do telefone → Estado da bateria.
  Em muitos modelos, o código `*#0228#` no Telefone também mostra o estado da bateria.
- **Desempenho:** em Assistência do aparelho, desligue a otimização automática agressiva se ela
  encerrar apps que a pessoa quer manter.

**Debloat:**

| Nível | Pacotes |
|---|---|
| 1 (seguro) | `com.facebook.services`, `com.facebook.system`, `com.facebook.appmanager`, `com.samsung.android.app.tips` (Dicas), `com.samsung.android.app.spage` (Samsung Free), `com.microsoft.skydrive` (OneDrive, se não usa) |
| 2 (perde função) | `com.samsung.android.bixby.agent` e `com.samsung.android.bixby.wakeup` (Bixby Voz), `com.samsung.android.visionintelligence` (Bixby Vision), `com.samsung.android.ardrawing` (AR Doodle), `com.samsung.android.aremoji` (AR Emoji) |
| 3 (nunca) | `com.samsung.android.lool` (Assistência do aparelho), pacotes Knox (`com.samsung.android.knox.*`, `com.sec.enterprise.*`), `com.sec.android.app.launcher`, `com.samsung.android.honeyboard` (teclado), `com.samsung.android.game.gos`, `com.samsung.android.dialer`, `com.samsung.android.incallui` |

## Motorola

- O sistema é próximo do Android puro, com pouco bloatware. O que costuma sair: apps de operadora,
  instaladores de parceiros e jogos pré-instalados.
- Não remova os apps "Moto", como `com.motorola.actions` (gestos) e a tela de notificações, se a pessoa
  usa os gestos.

## Google Pixel

- Pouco bloatware. Em geral, o ganho vem de espaço, RAM, reinício e temperatura.
- **Saúde da bateria:** Configurações → Bateria → Saúde da bateria (modelos mais novos).
  **Carregamento adaptável** reduz o desgaste.

## Oppo, Realme, OnePlus (ColorOS, realme UI, OxygenOS)

**Caso documentado:** em 2021, testes mostraram que o OnePlus 9 e o 9 Pro limitavam o desempenho de
apps populares, como navegadores e redes sociais, mas não o de benchmarks. A Geekbench retirou os
modelos do ranking. A OnePlus disse que era para economizar bateria e, depois, ofereceu um modo de
desempenho. Procure listas de pacotes junto de limites de frequência nas configurações do sistema.

- O gerenciador de bateria, `com.coloros.safecenter` e o launcher do fabricante ficam no nível 3.
- Desligue a "otimização de bateria inteligente" só para os apps que precisam rodar sempre.

## Huawei e Honor

**Caso documentado:** em 2018, testes mostraram que modelos Huawei e Honor aumentavam o desempenho ao
detectar benchmarks. Depois a empresa passou a oferecer um "modo de desempenho" ao usuário.

## Como checar limitação seletiva em qualquer marca

Na coleta, procure listas de pacotes junto de limites de frequência ou de FPS:

```
grep -il "benchmark\|antutu\|geekbench" coleta/06_fs_scripts_configs/conteudo_configs.txt
grep -i "scaling_max_freq\|max_freq\|cpu_limit\|fps" coleta/06_fs_scripts_configs/conteudo_configs.txt | head -50
```

Também procure perfis por jogo ou por app dentro dos APKs do fabricante, com `analisar_apks.py
--pasta`, depois de copiar os APKs do serviço de jogos e de desempenho com `adb pull`.
