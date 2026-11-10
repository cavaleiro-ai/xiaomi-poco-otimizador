# Estudo da câmera: o que medir e o que dá para melhorar

## 1. Medir

```
python scripts/resumo_camera.py --saida analise/camera.md
```
Sem `--arquivo`, ele lê do aparelho e salva os dados brutos em `camera_bruto/`. O resultado mostra:

- quantas câmeras o sistema tem e quantas ficam visíveis para apps comuns;
- o nível Camera2 de cada uma;
- a resolução exposta, comparada com a anunciada;
- suporte a RAW e a controle manual;
- estabilização óptica (OIS) e eletrônica (EIS);
- vídeo em alta velocidade;
- os perfis de gravação usados por apps de terceiros.

## 2. Interpretar

| Achado | Significado prático |
|---|---|
| Nível LEVEL_3 ou FULL, com RAW e MANUAL_SENSOR | Aceita apps avançados (portas da GCam, apps de foto manual/RAW) |
| Nível LIMITED ou LEGACY | Apps alternativos ganham pouco; foque no app nativo |
| "Sensor exposto" bem menor que o anunciado (ex.: 12 MP num sensor de 108 MP) | O sensor agrupa pixels (binning). A resolução total só existe no modo de alta resolução do app nativo |
| Câmeras ESCONDIDAS (ultra-angular, macro, profundidade) | Apps de terceiros não as enxergam. O fabricante libera só para apps de uma lista interna, e mudar essa lista exige root |
| Perfis de vídeo até 1080p30 | Apps de terceiros gravam no máximo isso pelo caminho padrão; o app nativo pode oferecer 4K e 60 fps |
| OIS "não" | Fotos noturnas e vídeo dependem de EIS e empilhamento: use apoio, modo noite e boa luz |
| Cenário CAMERA no log térmico | A câmera também sofre limites térmicos; gravações longas no calor perdem qualidade ou param |

## 3. O que melhora de verdade (do maior para o menor ganho)

1. **Configurações do app nativo:**
   - Ligue o modo de alta resolução (ex.: 50, 108 ou 200 MP) para fotos com boa luz.
   - Use 4K30 ou 1080p60 com estabilização no vídeo.
   - Deixe o HDR em automático, desligue filtros de beleza e marcas d'água e ative o modo Pro/RAW, se
     houver.
2. **Condições do aparelho:**
   - Limpe a lente.
   - Tire a capa que encosta na lente.
   - Mantenha espaço livre: com o armazenamento cheio, a gravação engasga.
   - Evite usar a câmera com o aparelho quente: o limite térmico reduz o processamento.
3. **App alternativo:** se o nível for FULL ou LEVEL_3, uma porta da GCam compatível com o modelo pode
   melhorar HDR e fotos noturnas. Cuidados:
   - Só de fontes conhecidas, porque é um APK instalado manualmente; rode `analisar_apks.py` nele antes.
   - Pode não acessar as câmeras escondidas.
   - A pessoa decide e instala; a skill não baixa APKs sozinha.
4. **Desempenho do app:** abertura lenta e atraso no disparo melhoram com RAM livre, armazenamento
   folgado e menos apps em segundo plano. Use as fases 4 e 5 do fluxo.

## 4. O que não muda

- A resolução e o tamanho do sensor, a lente e a existência de OIS.
- Os limites de vídeo do HAL: se o hardware não lista 4K60, nenhum app grava 4K60.
- O acesso de apps de terceiros às câmeras escondidas, a menos que haja root.
- Propriedades de câmera (`persist.vendor.camera.*`): só root altera, e mudar às cegas pode quebrar a
  câmera.
