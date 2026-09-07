# Matriz algoritmo × teste

Esta tabela é o quadro de acompanhamento. `✓` significa que há evidência no
repositório; `API` significa apenas que construtor/configuração foram validados;
`piloto` não é resultado do protocolo; `—` ainda precisa ser executado.

## Detecção

| Algoritmo | Código | Sintético/smoke | Busca treino | Refinar top 5 | 2 finalistas: val completa | Congelar | Teste 24/38/47/54 | 5-fold OOF | Aplicar 65 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Threshold fixo | ✓ | ✓ | piloto | duas finalistas preservadas | ✓ vídeos 14/19/36/52 | ✓ T200/o1/c2 | — | — | — |
| Otsu | ✓ | ✓ sintético | piloto | — | — | — | — | — | — |
| Adaptativo | ✓ | ✓ sintético | piloto | — | — | — | — | — | — |
| Threshold híbrido | ✓ | ✓ | — | — | — | — | — | — | — |
| Blob | ✓ | ✓ sintético | exploração | — | — | — | — | — | — |
| MOG2 | ✓ | ✓ sintético/reset + executor temporal | exploração | — | — | — | — | — | — |
| KNN | ✓ | ✓ sintético/reset + executor temporal | — | — | — | — | — | — | — |
| Watershed | ✓ | ✓ sintético | exploração | — | — | — | — | — | — |
| YOLO | ✓ | ✓ wrapper lazy/fake; piloto real | piloto 16/4 | — | — | — | — | — | — |

As configurações `T200/o1/c2` e `T190/o1/c1` foram executadas nos quatro vídeos
completos de validação. T200 venceu em F1 macro por vídeo e erro de contagem;
T190 reteve a vantagem de recall. A decisão foi registrada e T200 foi
congelado antes da execução confirmatória. Os quatro vídeos do holdout já
apareceram no piloto frame a frame antigo; por isso ele não é totalmente cego,
mas aquelas observações legadas não entram na seleção atual. O smoke curto
apenas validou o executor e não entra na tabela científica final.
O avaliador secundário YOLO/mAP também está validado estruturalmente, mas ainda
precisa de pesos novos para produzir evidência no split oficial.
MOG2 e KNN agora possuem uma bancada específica para clipes distribuídos no
treino, com `>=100` frames de aquecimento descartados e agregação macro por
vídeo. Nenhuma bateria VISEM desse grid foi executada durante a organização.

## Tracking

| Algoritmo | Código | Teste sintético | Boxes GT: tuning/val | Detector congelado: tuning/val | Congelar | Teste | 5-fold | Aplicar 65 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Centroide guloso | ✓ | ✓ | — | — | — | — | — | — |
| Húngaro | ✓ | ✓ | — | — | — | — | — | — |
| SORT | ✓ | ✓ | — | — | — | — | — | — |
| ByteTrack-style | ✓ | ✓ | — | — | — | — | — | — |
| Adaptive Flow-SORT | ✓ | ✓ | — | — | — | — | — | — |

O adaptador para TrackEval existe; HOTA, IDF1 e MOTA completos continuam
pendentes de execução com a dependência externa. Os contadores locais de
associação, ID-switch e fragmentação são auditoria, não substitutos dessas
métricas.

## Movimento aparente

| Algoritmo | Código | Translação sintética | Busca/val real | Máscara/ablação | Congelar | Teste | Cache 85 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Lucas–Kanade | ✓ | ✓ | — | ✓ contrato; VISEM — | — | — | — |
| Farneback | ✓ | ✓ | — | ✓ contrato; VISEM — | — | — | — |
| Horn–Schunck | ✓ | ✓ translação pequena, single-scale | — | ✓ contrato; VISEM — | — | — | — |
| RAFT | ✓ | sem torch/pesos | — | ✓ contrato; VISEM — | — | — | — |
| Híbrido robusto CPU | ✓ | ✓ fusão e translação sem compensação | — | ✓ contrato; VISEM — | — | — | — |
| Híbrido robusto + RAFT | ✓ | sem torch/pesos | — | ✓ contrato; VISEM — | — | — | — |

O contrato de máscara une boxes dos dois frames e o enriquecimento de tracks
foi validado com vetores conhecidos e pixels inválidos. A coluna ainda marca
`VISEM —` porque a ablação real mascarado/não mascarado não foi executada.

## Predição

| Algoritmo | Código | Analítico/sintético | GT: tuning/val | Tracker: tuning/val | Congelar | Teste | 5-fold | Aplicar 65 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Persistência | ✓ | ✓ | — | — | — | — | — | — |
| Velocidade constante | ✓ | ✓ | — | — | — | — | — | — |
| Kalman | ✓ | ✓ | — | — | — | — | — | — |
| Filtro de partículas | ✓ | ✓ | — | — | — | — | — | — |
| LSTM sem fluxo | ✓ | API; treino pendente | — | — | — | — | — | — |
| LSTM com fluxo | ✓ | API; treino pendente | — | — | — | — | — | — |
| Híbridos clássicos flow-aware | ✓ | ✓ | — | — | — | — | — | — |

## Próxima sessão: teste isolado do threshold

1. Conferir a seleção e o YAML congelado já registrados.
2. Fazer commit do estado limpo e executar uma única bateria confirmatória nos
   vídeos `24, 38, 47, 54`, registrando a exposição histórica como limitação.
3. Manter as runs de validação em `data/tests/` e gravar somente o teste
   congelado para `data/results/`.
4. Agregar o resultado por vídeo e registrar falhas visuais, latência e memória.
5. Produzir a confirmação 5-fold congelada e, em seguida, iniciar o mesmo ciclo
   para Otsu e threshold adaptativo.

Os comandos vigentes estão em [`script/README.md`](../../script/README.md).
