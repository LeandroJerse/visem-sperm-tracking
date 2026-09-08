# Baselines de predição com referência individual — protocolo v1

## Estado e objetivo

Protocolo prospectivo de 08/09/2026, definido antes da execução desta bateria.
O plano operacional é
[`prediction_baselines_v1.yaml`](../../configs/protocol/prediction_baselines_v1.yaml),
com identificador `prediction_baselines_v1_20260908`. Ainda não há resultados
de predição deste marco. Implementação, testes, registro do código e execução
deverão respeitar as regras abaixo.

O objetivo é medir duas referências determinísticas, persistência e velocidade
constante, sobre as mesmas trajetórias individuais anotadas do treino. Isso
isola a extrapolação de posições quando o histórico é fornecido pelo GT. Não
mede a pipeline completa com erros de detecção ou associação, não constitui
confirmação independente e não testa a hipótese de contribuição do fluxo
óptico. Essa hipótese permanece como objetivo posterior do TCC, conforme o
[protocolo geral](PROTOCOLO.md) e a
[revisão científica](../projeto/REVISAO_GERAL_20260908.md).

Não haverá busca de hiperparâmetros, seleção de vencedor, promoção de método,
teste de hipótese ou intervalo de confiança nesta bateria. Os parâmetros
abaixo são escolhas operacionais fixas, registradas antes dos resultados.

## Referência, universo e elegibilidade

A única entrada científica será a referência derivada já preparada e conferida
sob o [contrato de trajetórias individuais](TRAJETORIAS_INDIVIDUAIS_V1.md).
Serão usadas **todas as 343.776 janelas** de histórico 20, futuro 10 e stride 1
dos 12 vídeos de treino. As contagens abaixo são propriedades dessa preparação
anterior; não são resultados dos preditores.

| Vídeo | Janelas comuns aos dois métodos |
|---|---:|
| 11 | 52.223 |
| 12 | 34.093 |
| 13 | 60.406 |
| 15 | 23.315 |
| 21 | 30.574 |
| 22 | 14.944 |
| 23 | 2.922 |
| 29 | 4.058 |
| 30 | 14.582 |
| 35 | 43.998 |
| 60 | 18.802 |
| 82 | 43.859 |
| **Total** | **343.776** |

O YAML identifica o manifesto da preparação de `33d191d` e a conferência
independente por caminho e SHA-256. O hash do manifesto de referência é
`88965912d7f08bc6e2fe5ae69b20cf2c58fa538a8d99e3e5eb296722e6028c35`;
o da conferência aprovada é
`f751652ce01d4b830196da076bc038e4517568444b0563bde782bfeb457e39f9`.
A configuração também fixa o hash do split vigente. Esses vínculos deverão
ser conferidos, juntamente com os artefatos necessários da referência, sem
substituir silenciosamente a entrada por outra preparação.

Serão lidos apenas os produtos derivados autorizados de treino. Não serão
abertos vídeos, imagens ou anotações originais, nem fontes de validação ou
teste. Não serão executados detector, rastreador ou estimador de fluxo. O
congelamento de T218 para desenvolvimento não transforma esta bateria com GT
em uma avaliação do detector ou em uma execução de teste.

Permanecem as classes individuais 0/2, seus IDs textuais originais e os índices
originais de quadro. Janelas não cruzam vídeo, identidade, split ou interrupção
de observações. Indivíduos explicitamente anotados dentro de caixas cluster
continuam preservados. A elegibilidade já registrada exige futuro completo;
portanto, os erros serão condicionais à disponibilidade dessa referência. Não
será acrescentado filtro por velocidade, deslocamento, posição, classe entre
0/2, tamanho do segmento ou desempenho. Observações e segmentos sem janela
continuam no produto pai e na descrição da cobertura, sem erro imputado zero.

## Entradas causais e métodos fixos

Para uma origem de previsão `t`, o histórico contém as 20 posições
`p(t−19), ..., p(t)`. Os alvos são `p(t+1), ..., p(t+10)` e deverão ser
entregues separadamente à avaliação. A posição é o centro anotado `(x, y)`
em pixels da imagem original. Ambos os métodos receberão o mesmo histórico,
sem acesso a alvos futuros, classes futuras, fluxo ou informações de outras
janelas.

### Persistência — `persistence`

Para cada passo `h = 1, ..., 10`:

`p_prevista(t+h) = p(t)`.

Este método usa somente a última posição. Receber 20 posições não significa
usar todas elas; as 19 anteriores não entram no cálculo. Não possui parâmetro
a selecionar e constitui uma referência útil também quando a estimativa de
velocidade é ruidosa. Não se presume que outro método necessariamente o supere.

### Velocidade constante — `cv_median5`

As seis últimas posições, `p(t−5), ..., p(t)`, fornecem cinco diferenças:

`d(j) = p(j) − p(j−1)`, para `j = t−4, ..., t`.

A velocidade será a mediana calculada separadamente para cada componente:

`v = (mediana(dx), mediana(dy))`.

Para cada passo `h = 1, ..., 10`:

`p_prevista(t+h) = p(t) + h × v`.

São cinco diferenças e seis posições, não cinco posições. As outras 14
posições do histórico comum não entram nesta estimativa. A operação não é
mediana das magnitudes, média das diferenças ou ajuste aprendido. A janela 5
e a mediana são fixas para este marco; alternativas existentes no catálogo do
algoritmo não fazem parte desta execução.

### Coordenadas e tempo

Entradas, previsões e cálculos usarão `float64`, sem arredondamento de
apresentação no armazenamento. Não haverá clipping ao quadro nem normalização
de posições ou velocidades. Uma posição prevista fora da imagem permanece
como previsão e recebe seu erro em relação ao alvo disponível.

Os horizontes são definidos em **quadros**, não em uma duração física comum.
O FPS registrado no `input_contract.json` exportado pelo pai deverá acompanhar
o resumo de cada vídeo, com as durações nominais `H/FPS` para H = 1/5/10.
As 20 posições históricas cobrem 19 intervalos, isto é, `19/FPS` segundos
nominais. Não haverá nova leitura do vídeo nem reamostragem temporal. Esses
metadados não convertem deslocamento de imagem em velocidade física de fluido.

## Métricas densas de deslocamento

Para cada janela `w` e passo `h`, definir:

`e(w,h) = sqrt((x_previsto − x_GT)² + (y_previsto − y_GT)²)`.

Para H = 1, 5 e 10, registrar separadamente, em pixels:

`ADE_H(w) = [e(w,1) + ... + e(w,H)] / H`;

`FDE_H(w) = e(w,H)`.

Serão previstas e preservadas todas as posições dos passos 1 a 10. ADE_5
usa os cinco erros consecutivos e ADE_10 usa os dez. A média apenas dos passos
1, 5 e 10 não será chamada ADE_10. ADE_1 e FDE_1 devem coincidir. Não haverá
combinação ponderada dos seis indicadores em um placar único.

## Agregação e pareamento

A unidade estatística continua sendo o vídeo. As janelas consecutivas se
sobrepõem, e segmentos, células e clipes de um mesmo vídeo não serão tratados
como réplicas independentes. A agregação principal de cada indicador seguirá
esta ordem:

1. Calcular a média das janelas de cada par `(video_id, track_id original)`.
   Reunir todas as janelas dos segmentos daquele ID antes dessa média.
2. Calcular a média com peso igual entre os IDs com janela dentro do vídeo.
3. Calcular a média com peso igual entre os 12 vídeos.

Um ID que aparece em segmentos com quantidades diferentes de janelas não
receberá peso adicional por ter sido fragmentado. Não se calculará primeiro
uma média com peso igual entre seus segmentos. IDs textuais iguais em vídeos
diferentes continuam sendo unidades distintas. Para cada ID, registrar número
de janelas e de segmentos usados; para cada vídeo, registrar a quantidade de
IDs com janela e a cobertura efetivamente comum aos métodos.

Como complemento descritivo, calcular a média de todas as janelas dentro de
cada vídeo e depois a média com peso igual entre os 12 vídeos. Nesse resumo,
IDs com mais janelas influenciam mais a média do respectivo vídeo. Ele mostra
a sensibilidade ao comprimento disponível das trajetórias e deve permanecer
identificado como agregação secundária. Não equivale a reunir todas as janelas
dos 12 vídeos em uma média global ponderada pela quantidade de janelas.

Os dois métodos deverão produzir resultados para exatamente os mesmos
`window_id`, IDs, segmentos e origens. O resumo pareado por vídeo registrará
as diferenças `cv_median5 − persistence` de cada indicador, para as agregações
declaradas; diferença negativa significa erro menor da velocidade constante.
Nenhuma falha autoriza remover uma janela difícil e continuar a comparação
com um subconjunto. Não haverá p-valor ou intervalo de confiança nesta etapa
descritiva no treino, em conformidade com os
[cuidados estatísticos](ESTATISTICA_E_PARETO.md).

## Implementação e exportação previstas

| Responsabilidade | Caminho previsto |
|---|---|
| Plano | `configs/protocol/prediction_baselines_v1.yaml` |
| Leitura protegida da referência | `src/prediction/reference.py` |
| Predição em lotes | `predict_batch` das duas classes clássicas |
| Erros densos | `dense_trajectory_metrics` em `src/prediction/metrics.py` |
| Coordenação da bateria | `src/experiments/prediction_baselines.py` |
| Executor | `script/prediction/test/evaluate_baselines.py` |

A saída será uma nova run sob
`data/tests/prediction/baselines/<configuration>/development/<run>/`.
Cada diretório `by_video/<video>/<persistence|cv_median5>/` conterá:

- `predictions.csv`: uma linha por janela, com identidade e as dez posições
  previstas completas;
- `window_metrics.csv`: uma linha por janela, com identidade e ADE/FDE para
  H = 1/5/10;
- `track_metrics.csv`: contagens e médias por ID original, reunindo segmentos;
- `summary.json`: cobertura, metadados temporais e agregações daquele método
  no vídeo.

No topo estarão `video_metrics.csv`, `paired_video_metrics.csv`, `summary.json`
e `manifest.json`, com o plano resolvido e sua proveniência. São 24 combinações
vídeo–método e 12 pares de vídeo, sem multiplicação da unidade estatística.

O esquema de `predictions.csv` será declarado como
`wide_dense_positions_v1`: colunas de identidade
`window_id, video_id, track_id, segment_id, split, history_start, origin_frame, future_end`, seguidas de
`cx_h1, cy_h1, ..., cx_h10, cy_h10`. O CSV terá precisão suficiente para
reconstituir os valores `float64`, sem arredondamento decimal fixo. O arquivo
de métricas também usará uma linha por janela com os seis indicadores.

Haverá **687.552 linhas em cada família de CSV** de previsões e métricas,
somando os dois métodos. As previsões representam 6.875.520 posições futuras
e 13.751.040 valores de coordenadas; o esquema largo evita repetir a identidade
em uma linha para cada passo. Os alvos não serão duplicados: cada `window_id`
referencia os índices e observações do pai, protegidos por hashes. A referência
imutável continuará sendo uma dependência necessária para reconstituir erros.

O formato longo de execuções anteriores não será reescrito. Consumidores
deverão reconhecer o esquema declarado ou rejeitá-lo explicitamente; o nome
`predictions.csv` sozinho não demonstra compatibilidade entre esquemas.

## Custos, integridade e falhas

O plano fixa processamento em lotes de 512 janelas, na ordem registrada dos
vídeos e depois dos métodos. A implementação deverá limitar as estruturas em
memória ao vídeo e ao lote necessários, escrever CSVs progressivamente e
acumular somas e contagens por ID. Não será necessário manter uma lista de
todos os registros de saída em memória.

O orçamento prospectivo é de 1.200 segundos de limite brando de tempo,
2.048 MiB de RSS amostrado e 3.072 MiB de artefatos. Uma estimativa inicial de
400–600 MiB para os CSVs largos é apenas projeção, não medição nem garantia
de conclusão no tempo previsto. RSS amostrado também não garante observar
todo pico instantâneo. A run deverá registrar tempo, consumo observado e
tamanho real; distinguir, quando disponível, leitura/verificação, cálculo e
gravação do custo total da bateria.

A seed 42 identifica a execução e o protocolo; os dois métodos não usam
aleatoriedade. Repetir seeds não criaria novas réplicas científicas. Serão
registrados configuração resolvida, commit, estado do Git, hashes do código,
ambiente, recursos, plano, referência e artefatos produzidos.

As entradas derivadas e suas identidades deverão ser verificadas antes da
execução e novamente antes de aceitar a comparação. Leituras incompletas,
valores inválidos ou não finitos, divergência de hash, janela ausente, erro de
gravação ou orçamento excedido deverão preservar a run parcial e seu motivo.
Não haverá sobrescrita, descarte silencioso de registros nem resumo comparativo
aceito antes de ambos os métodos completarem todas as janelas dos 12 vídeos.

## Conferência e interpretação posterior

Antes da execução, testes sintéticos deverão cobrir a indexação temporal,
a mediana das cinco diferenças, a persistência, o cálculo denso de ADE,
a ausência de clipping e o retorno fiel de floats exportados. Alterar somente
os alvos futuros mantendo o histórico fixo não poderá mudar as previsões.
A agregação deverá ser exercitada com IDs de quantidades diferentes de
janelas e com segmentos de comprimentos diferentes pertencentes ao mesmo ID.

Uma conferência independente posterior deverá usar somente JSON/CSV exportados
e a referência derivada autorizada, sem importar a implementação científica
nem abrir fontes originais. Deverá reconstruir as previsões, os erros densos,
as contagens, os pesos por ID/vídeo e o pareamento de todas as janelas, além de
conferir hashes e cobertura. Falhas de execução ou de conferência serão
preservadas e explicadas; nenhuma conferência é declarada concluída aqui.

Mesmo que um baseline apresente erro menor, a conclusão se limitará a essas
referências fixas, ao treino e às janelas elegíveis com GT. A hipótese principal
exigirá comparar modelos equivalentes com e sem características de fluxo,
sob causalidade e seleção apropriadas. Se o fluxo introduzir uma regra adicional
de disponibilidade ou validade, a comparação posterior deverá declarar uma coorte
comum e recalcular ambos os braços sobre as mesmas origens. Não será válida
a comparação entre o resumo integral desta bateria e um método com fluxo
avaliado somente em um subconjunto favorável.

Finalmente, as interrupções usadas para construir janelas não definem por si
só a política de identidades ou associação da avaliação HOTA. Este marco não
altera o contrato de tracking, a separação por vídeo ou o bloqueio do teste.
