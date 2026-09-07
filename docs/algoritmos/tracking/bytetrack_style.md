# ByteTrack-style

## Onde encontrar

| Procurar | Abrir |
|---|---|
| Implementação | [bytetrack_style.py](../../../src/tracking/modern/bytetrack_style.py) — `ByteTrackStyleTracker` · [SORT reutilizado](../../../src/tracking/classical/sort.py) |
| Configuração | [YAML de desenvolvimento](../../../configs/tracking/bytetrack_style/search.yaml) |
| Execução | [Comandos oficiais](../../../script/README.md#2-tracking) |
| Ensaios e resultados | [Área de ensaios do domínio](../../../data/tests/tracking/README.md) · [Área de resultados promovidos](../../../data/results/tracking/README.md) |

A classe reutiliza o SORT e implementa sua associação em dois estágios; é uma variante no estilo ByteTrack, com nome experimental próprio.

Ainda não há pasta de runs específica deste método; o link abre a área do domínio.

[Índice da família](README.md) · [Catálogo de algoritmos](../README.md)

## Escopo correto do nome

Esta implementação testa a ideia central do ByteTrack: utilizar detecções de
baixa confiança para recuperar tracks, sem permitir que elas iniciem novos IDs.
Ela usa o mesmo Kalman e IoU/Húngaro do SORT. Não reproduz todos os pools e
detalhes do código oficial; por isso o nome público é `bytetrack_style`, e não
“ByteTrack oficial”.

## Associação em dois estágios

1. dividir detecções em alta (`score >= high_threshold`), baixa
   (`low_threshold <= score < high_threshold`) e descartada;
2. associar todas as tracks às detecções altas;
3. associar as tracks ainda livres às detecções baixas, com
   `second_iou_threshold` próprio;
4. criar novas tracks somente com detecções altas não associadas cujo score
   alcance `new_track_threshold`.

## Parâmetros exclusivos

| Parâmetro | Função |
|---|---|
| `high_threshold` | separa detecções confiáveis |
| `low_threshold` | menor score reutilizável |
| `new_track_threshold` | score mínimo para criar ID |
| `second_iou_threshold` | gate do segundo estágio |

Os demais parâmetros vêm do SORT. A varredura de scores só faz sentido com um
detector que produza confiança calibrável, especialmente YOLO. Aplicar scores
constantes iguais a 1 reduz o método essencialmente ao SORT.

## Pontos fortes

- recupera células parcialmente ocultas ou de contraste momentaneamente baixo;
- reduz fragmentação sem exigir rede de aparência;
- mantém custo próximo ao SORT.

## Pontos fracos

- depende criticamente da calibração dos scores;
- limiar baixo pode associar ruído a tracks existentes;
- não resolve ambiguidades de aparência ou cruzamento;
- esta versão não deve ser comparada como reprodução exata do pacote oficial.

## Testes obrigatórios

- baixa confiança recuperando o mesmo ID;
- baixa confiança isolada sem criação de track;
- varredura conjunta dos três limiares;
- comparação pareada SORT × ByteTrack-style com o mesmo detector YOLO.

Status: dois estágios e regras de criação validados sinteticamente; avaliação
VISEM pendente.
