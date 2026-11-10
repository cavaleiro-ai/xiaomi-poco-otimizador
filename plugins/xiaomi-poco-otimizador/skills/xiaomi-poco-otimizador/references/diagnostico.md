# Interpretação do diagnóstico

## Sumário
1. Limiares por indicador
2. Onde procurar cada coisa na coleta
3. Obsolescência programada: o que conta como evidência
4. Overclock e "desempenho máximo"
5. Causas de lentidão mais comuns, por ordem de frequência

## 1. Limiares por indicador

| Indicador | De onde vem | Normal | Atenção | Grave |
|---|---|---|---|---|
| Espaço livre em /data | `df -k /data` | ≥ 20 % | 10–20 % | < 10 % (o flash fica lento e o Android rebaixa a otimização de apps) |
| Tempo ligado | `/proc/uptime` | < 7 dias | 7–20 dias | > 20 dias com travadas |
| RAM disponível | `MemAvailable` | > 25 % | 15–25 % | < 15 % |
| Troca para swap | `pswpout` × 4 KB ÷ dias ligado | < 3 GB/dia | 3–10 GB/dia | > 10 GB/dia (thrashing) |
| Apps encerrados por falta de memória | `oom_kill` em `/proc/vmstat` | < 50 | 50–200 | > 200 desde o boot |
| Pressão de memória | `/proc/pressure/memory`, `some avg300` | < 5 % | 5–10 % | > 10 % |
| Capacidade da bateria | `Estimated battery capacity` ÷ capacidade de fábrica | ≥ 85 % | 80–85 % | < 80 % (trocar a bateria) |
| Temperatura da bateria | `dumpsys battery` (décimos de °C) | < 37 °C | 37–40 °C | ≥ 40 °C (cortes de carga e desempenho, desgaste químico) |
| CPU limitada agora | `scaling_max_freq` < `cpuinfo_max_freq` | igual | limitada com o aparelho quente | limitada com o aparelho frio |
| Vida do flash (UFS/eMMC) | `bDeviceLifeTimeEstA/B` ou `life_time` | 0x01–0x03 | 0x04–0x07 | ≥ 0x08 (70 %+ consumida) |
| Escrita no flash | `dumpsys storaged` | < 20 GB/dia | 20–50 GB/dia | > 50 GB/dia (swap no flash ou app escrevendo sem parar) |

Notas:
- A capacidade de fábrica raramente é legível sem root. Use a ficha técnica do modelo. O Android só
  estima a capacidade depois de alguns ciclos completos de carga.
- `Thermal Status` 0 no `dumpsys thermalservice` não prova ausência de limitação. Vários fabricantes,
  como a Xiaomi com o mi_thermald, limitam por um serviço próprio que não passa por esse status.
- Os códigos de vida do flash seguem o padrão JEDEC: 0x01 = 0–10 % consumida, 0x02 = 10–20 %, e assim
  por diante; 0x0B = vida útil excedida. O tipo A e o tipo B medem tipos de célula diferentes.

## 2. Onde procurar cada coisa na coleta

| Pergunta | Arquivo (dentro da pasta da coleta) | O que procurar |
|---|---|---|
| Quem gasta bateria | `03_dumpsys/zz_batterystats_full.txt` | "Estimated power use", "Wake lock", "Kernel Wake lock", "Foreground service" |
| Quem fica em segundo plano | `03_dumpsys/zz_activity_services.txt`, `zz_procstats_24h.txt` | ServiceRecord por pacote; processos com mais tempo em memória |
| Travadas e fechamentos | `09_logs/dropbox_list.txt`, `logcat_main_system_crash.txt` | `data_app_anr`, `data_app_crash`, `system_app_anr`, "ANR in", "FATAL EXCEPTION" |
| Tarefas e alarmes de cada app | `03_dumpsys/zz_jobscheduler.txt`, `zz_alarm.txt` | contagens por pacote |
| Isenções de economia de bateria | `07_apps/doze_whitelist.txt` | linhas `user,` (por escolha do usuário ou do fabricante) |
| Apps "raros" ou restritos | `07_apps/standby_buckets.txt` | baldes 10 = ativo, 20 = conjunto de trabalho, 30 = frequente, 40 = raro, 45 = restrito, 50 = nunca usado |
| Restrições de segundo plano | `07_apps/bg_restrictions_appops.txt` | `RUN_ANY_IN_BACKGROUND: ignore` |
| Acessibilidade, administrador, VPN | `07_apps/accessibility_admin_roles.txt`, `03_dumpsys/zz_device_policy.txt` | serviços e administradores desconhecidos (risco de espionagem) |
| Apps fora da loja | `07_apps/packages_third_party.txt` | instalador diferente da Play Store ou da loja do fabricante |
| Temperaturas e limites | `04_sysfs/thermal_zones_cooling.txt`, `08_processos/cpufreq_snapshot.txt` | sensores quentes; frequências abaixo do máximo |
| Configurações térmicas e de desempenho | `06_fs_scripts_configs/_lista_configs.txt`, `conteudo_configs.txt` | arquivos thermal, perf, powerhint, game, refresh |
| Scripts de inicialização | `06_fs_scripts_configs/conteudo_sh_rc.txt` | `on property:`, escritas em `scaling_max_freq`, `thermal`, `charge` |
| Flags remotas (nuvem) | `02_settings/device_config_flags.txt`, `02_settings/global.txt` | chaves com `cloud`, `thermal`, `perf`, `fps`, `battery` |
| Escrita no armazenamento | `03_dumpsys/zz_storaged.txt` | por app (bytes escritos, não `wchar`) |
| Saúde do UFS (Xiaomi) | bugreport: seção "UFS health desc" | `bDeviceLifeTimeEstA/B`, `bPreEOLInfo` |
| Log térmico interno (Xiaomi) | bugreport: `dumpstate_board.txt` | seções "THERMAL DUMP LOG" (use `analisar_termico_xiaomi.py`) |

Dicas:
- Os arquivos são grandes. Use grep com o nome do pacote ou da chave, nunca leia inteiros.
- A coleta é uma fotografia de um momento. Para medir tendência, como a temperatura ao jogar, peça à
  pessoa para usar o celular normalmente por alguns minutos e colete de novo só a parte rápida.

## 3. Obsolescência programada: o que conta como evidência

**Conta como evidência (relate com destaque, com arquivo e trecho):**
- Código ou configuração que reduz desempenho, brilho ou carga com base na **idade do aparelho, data,
  número de ciclos de carga, saúde da bateria ou versão do sistema**, sem ligação com temperatura ou
  segurança elétrica. Procure por `cycle_count`, `soh`, `aging`, `batt_age`, `degrad` e `lifetime`
  usados como entrada de limites de CPU, GPU ou carga.
- **Tratamento diferente por nome de app:** limites mais duros para apps populares ou liberação total
  só para benchmarks. Isso já foi documentado: a Samsung, com o Game Optimizing Service, em 2022; a
  OnePlus, com a limitação de apps populares no OnePlus 9, em 2021; e a Huawei, com o reforço para
  benchmarks, em 2018. Procure listas de pacotes junto de frequências ou de `benchmark` nos perfis.
- **Limites que pioram com atualizações** sem explicação. Compare versões, quando houver dados
  antigos.
- **Mecanismos escondidos do usuário:** configurações criptografadas, perfis baixados da nuvem que
  alteram limites, ou ausência de opção para desligá-los. Por si só isso não é obsolescência, mas
  reduz a transparência e merece registro.

**Não conta (mas descreva com números quando for agressivo):**
- Limitação por temperatura. Ela protege o chip, a bateria e o usuário. Ainda assim, limites que
  começam muito baixo, como cortar a CPU a 35 °C de sensor, são um achado legítimo de projeto
  agressivo e devem ser mostrados.
- Desgaste natural da bateria e do flash.
- Lentidão por armazenamento cheio, RAM saturada ou apps pesados.

**Limites da análise (diga sempre):** sem root não é possível ler partes do sistema nem descriptografar
configurações do fabricante. O comportamento pode ser reconstruído pelos logs, mas a intenção não pode
ser provada. Use "não foi encontrada evidência de X" em vez de "não existe X".

## 4. Overclock e "desempenho máximo"

- Sem root, as frequências máximas não podem ser elevadas. `cpuinfo_max_freq` é o teto do kernel e o
  `scaling_max_freq` atual mostra quanto a política está cortando. Mostre os dois à pessoa.
- O que recupera desempenho de verdade: reduzir a temperatura (tirar a capa para jogar, não jogar
  carregando, evitar sol e carro), ligar o modo de desempenho do fabricante, manter espaço e RAM
  folgados e remover apps que rodam o tempo todo.
- Root ou kernel customizado: fora do escopo. Os riscos são perda de apps de banco por falha de
  integridade, perda de garantia, instabilidade e risco de travar o aparelho. Se a pessoa insistir,
  explique esses riscos e indique que exige outro tipo de ajuda.

## 5. Causas de lentidão mais comuns, por ordem de frequência

1. Armazenamento com menos de 10–15 % livre.
2. RAM saturada: muitos apps residentes, extensão de memória no flash e swap intensa.
3. Política térmica agressiva somada a um aparelho quente (capa, carga rápida durante uso, mineradores
   ou apps presos em laço).
4. Bateria gasta: corta o pico de corrente e aciona limitadores com bateria fraca (BCL).
5. Apps de fábrica e de terceiros com serviços permanentes, anúncios e telemetria.
6. Muito tempo sem reiniciar.
7. Desgaste do flash (raro abaixo de 70 % de vida consumida).
