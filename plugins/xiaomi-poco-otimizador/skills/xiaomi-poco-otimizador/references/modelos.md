# Modelos de documento

Escreva para a pessoa dona do celular, em linguagem simples. Cada documento começa pelas conclusões. Os
números vão em tabelas e cada afirmação técnica cita o arquivo de origem. Marque cada achado como
**fato** (medido), **inferência** (deduzido dos dados) ou **hipótese** (possível, não verificado).

## Relatório de varredura: `RELATORIO_<modelo>_<data>.md`

```markdown
# Relatório — <marca modelo> (<codinome>, <sistema e versão>)

**Data da coleta:** <data> · **Método:** somente leitura via ADB, sem root · **Estado:** <bootloader, root, dias ligado>

## Conclusões
1. <achado mais importante, com o número que o sustenta e o que significa na prática>
2. ...
(5 a 8 itens, do mais grave ao menos grave)

## Obsolescência programada: veredito
<"Encontrada evidência de X" ou "Não foi encontrada evidência de degradação por idade, ciclos ou versão",
seguido do que FOI encontrado: limites térmicos, perfis por app, configurações criptografadas, e dos
limites da análise sem root>

## Evidências
### Bateria
### Temperatura e limitação de desempenho
### Memória e armazenamento
### Apps (pesados, fora da loja, sem uso, permissões de risco)
### Tela (brilho, taxa de atualização, limites)
### Câmera (se pedido)
(cada seção: tabela de medições + arquivo de origem + classificação fato/inferência/hipótese)

## O que fazer
<ações da pessoa e ações que o Claude pode aplicar com autorização, com ganho esperado>

## Limites desta análise
<o que não pôde ser lido sem root, o que é inferência>
```

## Plano de otimização: `PLANO_<modelo>_<data>.md`

```markdown
# Plano de otimização — <modelo>

## Diagnóstico em uma tabela
| Causa | Evidência | Peso |

## Fase A: ajustes que você faz na tela (5 minutos)
1. ...

## Fase B: o que eu aplico pelo ADB (com sua autorização, tudo reversível)
### Remoção nível 1 (seguro)
| Pacote | O que é | Por que remover | Efeito colateral |
### Remoção nível 2 (opcional, perde função)
### Restrição de segundo plano
| App | Consumo medido | Efeito |
### Limpeza de caches

## Fase C: espaço (backup e limpeza; exige destino e autorização separada)
| Pasta | Tamanho | Destino |

## Ganho esperado e como desfazer
```

## Registro de execução: `execucao/EXECUCAO_<data>.md`

```markdown
# Execução — <data e hora>

Autorização do dono: "<frase exata>"

## 1. <ação> — <resultado>
Comando: `...` · Resultado: N ok, M falhas · Desfazer: `RESTAURAR_....txt`

## Antes × depois
| Medida | Antes | Depois |
|---|---:|---:|
| Pacotes do usuário | | |
| Armazenamento livre | | |
| RAM disponível | | |

## Pendências para o dono
1. Reiniciar o aparelho.
2. ...

## Arquivos desta execução
```
