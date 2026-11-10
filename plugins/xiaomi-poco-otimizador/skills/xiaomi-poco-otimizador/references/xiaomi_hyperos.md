# Xiaomi, POCO e Redmi (HyperOS / MIUI)

## Sumário
1. Componentes que controlam desempenho, temperatura e bateria
2. Como ler a política térmica real (exemplo medido)
3. Restrições do ADB nesses aparelhos
4. Ajustes que a pessoa faz na tela
5. Debloat por níveis
6. Menus ocultos úteis

## 1. Componentes que controlam desempenho, temperatura e bateria

| Componente | O que faz | Observações |
|---|---|---|
| `mi_thermald` (daemon do vendor) | Decide os tetos de CPU, GPU, brilho, corrente de carga, modem e hotplug de núcleos a partir de um "sensor virtual", uma média ponderada de termistores | As configurações `/vendor/etc/thermal-*.conf` costumam vir **criptografadas**. Algumas, como `thermald-devices.conf` e `thermal-chg-only.conf`, são legíveis. A política real pode ser reconstruída pelo log interno no bugreport |
| `/sys/class/thermal/thermal_message/` | Interface entre o sistema e o mi_thermald: `sconfig` (cenário ativo: normal, câmera, vídeo, jogo…), `temp_state`, `board_sensor_temp` | Leitura liberada ao ADB na maioria dos modelos |
| Joyose (`com.xiaomi.joyose`) | Perfis de jogos e desempenho: tetos de CPU por jogo, FPS por temperatura (`dynamic_fps`), escala de resolução e perfis baixados da nuvem | Os perfis por modelo ficam dentro do APK (`assets/<modelo>/default_cloud_*.json`) |
| PowerKeeper (`com.miui.powerkeeper`) | Gerente de bateria: congela e encerra apps, aplica regras por temperatura da bateria | **Não remover**: quebra carga, economia e configurações de bateria |
| SmartPower, millet, greezer (framework) | Congelamento de apps em segundo plano | Sem root não há como alterar |
| "Extensão de memória" | Swap adicional no armazenamento flash | Ajuda com pouca RAM, mas aumenta a escrita no flash e a latência quando o armazenamento está cheio |

## 2. Como ler a política térmica real

O bugreport (gerado pelo `coletar.py`) traz o arquivo `dumpstate_board.txt`. Nele, as seções `THERMAL
DUMP LOG` e `LAST THERMAL DUMP LOG` têm cada decisão do mi_thermald com data, cenário, temperatura do
sensor virtual e limite aplicado. Rode:

```
python scripts/analisar_termico_xiaomi.py coleta/10_bugreport analise/termico.md
```

**Exemplo medido** (POCO X5 Pro 5G, Snapdragon 778G, HyperOS 2, cerca de 300 h de log) para mostrar o
tipo de conclusão que a análise permite:

| Sensor virtual | Teto dos núcleos grandes |
|---|---|
| < 35 °C | 2,40 GHz (máximo) |
| 35–37 °C | 2,05–1,90 GHz |
| 37–40 °C | 1,90–1,65 GHz |
| 40–41 °C | 1,52 GHz |
| 41–45 °C | 1,34–1,23 GHz |
| ≥ 45 °C | 0,94 GHz (0,69 GHz a 48 °C) |

Nesse aparelho, os núcleos grandes ficaram abaixo do máximo em cerca de 30 % do tempo. O brilho
máximo também foi limitado em cerca de 30 % do tempo, a partir de 37 °C. Com a tela acesa e quente, a
corrente de carga caía para perto de 3 W. A regressão do sensor virtual mostrou que os termistores
`quiet_therm`, `cpu_therm`, `battery` e `charger_therm` comandam os cortes. Por isso carregar e jogar
ao mesmo tempo dispara os limites muito cedo.

Ao relatar: o limite em si é proteção térmica, não obsolescência. Começar a cortar a 35 °C de sensor,
com o aparelho apenas morno, é uma escolha agressiva de projeto e deve ser mostrada com números.

## 3. Restrições do ADB nesses aparelhos

- `settings put` falha com `SecurityException: WRITE_SECURE_SETTINGS` se a opção "Depuração USB
  (configurações de segurança)" estiver desligada. Ela exige conta Xiaomi e SIM. Na falta dela, faça
  os ajustes pela tela.
- `input tap/keyevent` falha com `INJECT_EVENTS` pelo mesmo motivo.
- `pm uninstall -k --user 0` funciona para quase tudo. Alguns pacotes respondem `Failure [-1000]`, e o
  `remover_pacotes.py` os desativa com `pm disable-user`.
- Atividades internas de desempenho da Qualcomm (`com.qualcomm.qti.performancemode`) costumam estar
  desativadas pela MIUI e não abrem pelo `am start`.

## 4. Ajustes que a pessoa faz na tela

Os nomes variam entre MIUI 12–14 e HyperOS 1–2. Use a busca das Configurações.

1. **Modo de desempenho:** Configurações → Bateria → Modo de desempenho (ou "Desempenho máximo").
2. **Taxa de atualização:** Configurações → Tela → Taxa de atualização. "Padrão" (dinâmica) economiza
   bateria e esquenta menos. "Personalizado 120 Hz" é mais fluido e esquenta mais.
3. **Animações:** Opções do desenvolvedor → Escala de animação da janela, Escala de animação de
   transição e Escala de duração do Animator → 0,5x.
4. **Extensão de memória:** Configurações → Configurações adicionais → Extensão de memória. Desligue
   depois de liberar espaço e RAM e observe por alguns dias.
5. **Anúncios da MIUI:** Configurações → Senhas e segurança → Autorização e revogação → desligar "msa"
   (se o pacote não tiver sido removido). Desligue "Recomendações" nos apps Segurança, Arquivos,
   Downloads e Temas.
6. **Carga:** use o carregador original. Carregue com a tela apagada e sem capa, e evite carregar
   jogando ou ao sol.

## 5. Debloat por níveis

Sempre por `remover_pacotes.py`, que é reversível. Confirme que o pacote existe no aparelho; os nomes
mudam entre regiões (global, EEA, Índia, China).

### Nível 1: anúncios, telemetria e duplicados (seguro)

| Pacote | O que é | Efeito de remover |
|---|---|---|
| `com.miui.msa.global` | Serviço de anúncios da MIUI | Somem os anúncios dos apps da Xiaomi |
| `com.miui.analytics` | Telemetria | Nenhum perceptível |
| `com.xiaomi.discover` | Atualizador e promoções de apps do sistema | Apps de sistema deixam de se atualizar por ele |
| `com.miui.android.fashiongallery` | Carrossel de papéis de parede (Glance) | O carrossel some |
| `com.mi.globalminusscreen` | App Vault (painel à esquerda da tela inicial) | O painel some |
| `com.facebook.services`, `com.facebook.system`, `com.facebook.appmanager` | Instaladores e serviços do Facebook pré-instalados | Nenhum: o app do Facebook, se instalado, continua funcionando |
| `com.amazon.appmanager` | Instalador da Amazon pré-instalado | Nenhum |
| `com.xiaomi.mipicks` | GetApps (loja da Xiaomi) | Apps da Xiaomi deixam de se atualizar pelo GetApps |
| `com.xiaomi.glgm` | Xiaomi Games | Nenhum |
| `com.miui.videoplayer` | Mi Vídeo | Usar outro player |
| `com.miui.player` | Mi Música | Usar outro player |
| `com.mi.globalbrowser` | Navegador Mi | Usar Chrome ou outro navegador |
| `com.miui.bugreport`, `com.miui.miservice` | Feedback e "Serviços e feedback" | Perde o envio de feedback à Xiaomi |
| `com.miui.yellowpage` | Páginas amarelas | Nenhum fora da Índia e da China |

### Nível 2: perde uma função (remova só se a pessoa não usa)

| Pacote | Função perdida |
|---|---|
| `com.xiaomi.joyose` | Perfis de jogos da nuvem (o Game Turbo continua, sem perfis por jogo) |
| `com.miui.cloudservice`, `com.miui.cloudbackup`, `com.miui.micloudsync` | Mi Cloud (backup e sincronização Xiaomi) |
| `com.xiaomi.mirror` | Conexão com o PC (Mi Mirror) |
| `com.xiaomi.barrage` | Notificações flutuantes em jogos |
| `com.xiaomi.aiasst.vision` | Legendas por IA |
| `com.xiaomi.payment` | Mi Pay (não opera em vários países) |
| `cn.wps.xiaomi.abroad.lite` | WPS Office Lite |
| `com.miui.touchassistant` | Bola flutuante (Quick ball) |
| `com.xiaomi.midrop` | ShareMe (costuma só aceitar desativação) |
| `com.miui.screenrecorder` | Gravador de tela da MIUI |
| `com.miui.cleaner` | Limpador. Deixe por último: pode ser útil para liberar espaço antes |

### Nível 3: nunca remover

`com.miui.securitycenter` (Segurança: permissões, verificação de apps),
`com.miui.securitycore` e `com.miui.securityadd` (complementos de segurança),
`com.miui.powerkeeper` (bateria), `com.miui.daemon`, `com.xiaomi.finddevice` (Encontrar dispositivo;
removê-lo com a conta ativa pode gerar bloqueio), `com.xiaomi.xmsf` (push da Xiaomi),
`com.miui.guardprovider`, `com.xiaomi.account`, `com.miui.home` (launcher),
`com.lbe.security.miui` (gerente de permissões), `com.miui.packageinstaller` (instalação de apps),
`com.xiaomi.misettings`, `com.miui.miwallpaper`, `com.android.updater` (atualizações do sistema).
O `remover_pacotes.py` recusa todos esses.

## 6. Menus ocultos úteis

Digite no app Telefone:
- `*#*#6485#*#*`: informações da bateria. Os campos variam por modelo e alguns trazem dados de saúde
  ou ciclos. Peça uma foto da tela e interprete com cautela.
- `*#*#64663#*#*`: CIT, os testes de hardware de fábrica (tela, toque, sensores, câmeras, alto-falante).
  É útil para separar defeito de hardware de problema de software.
