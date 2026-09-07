# Mapa dos algoritmos de predição de trajetórias

[Catálogo](../README.md) · [Código e contratos](../../../src/prediction/README.md) · [Parâmetros](../../../configs/prediction/) · [Comandos oficiais](../../../script/README.md#4-predição) · [Ensaios](../../../data/tests/prediction/README.md) · [Resultados promovidos](../../../data/results/prediction/README.md)

Todos os preditores recebem um histórico `(tempo, x/y)` e retornam posições em
horizontes explícitos, por padrão 1, 5 e 10 frames. `PredictionResult` impede
misturar índices de vetor com horizontes reais.

| Família | Baseline puro | Variante com fluxo, documentada separadamente |
|---|---|---|
| Persistência | [Persistência](persistencia.md) | não aplicável |
| Velocidade | [Velocidade constante](velocidade_constante.md) | [Velocidade com fluxo](velocidade_constante_com_fluxo.md) |
| Kalman | [Kalman](kalman.md) | [Kalman com fluxo](kalman_com_fluxo.md) |
| Partículas | [Filtro de Partículas](filtro_particulas.md) | [Partículas com fluxo](particulas_com_fluxo.md) |
| LSTM | [LSTM sem fluxo](lstm.md) | [LSTM com fluxo](lstm_com_fluxo.md) |

As variantes `flow_aware_*` são algoritmos separados. Nos híbridos clássicos, o
fluxo acumulado é removido do histórico, o movimento intrínseco é estimado e o
fluxo futuro é então recomposto. Se não houver fluxo futuro, usa-se o último
vetor observado e a hipótese fica registrada.

`windows.py` cria somente janelas consecutivas, totalmente anotadas e contidas
em um único vídeo/split. Assim, lacunas do vídeo 23 são descartadas e um mesmo
vídeo nunca aparece simultaneamente em treino e teste. `metrics.py` fornece ADE,
FDE e erro por horizonte.

## Protocolo

1. Histórico de 20 frames; horizontes 1, 5 e 10.
2. Avaliar primeiro com trajetórias GT e depois fim a fim com o tracker.
3. Comparar todas as versões sem fluxo e com fluxo de maneira pareada.
4. Dividir exclusivamente por vídeo; nunca criar janelas antes do split.
5. Repetir modelos estocásticos com sementes 42, 123 e 2026.
6. Agregar primeiro por trajetória e depois por vídeo.

Resultados estão marcados como `pendente` até execução no desenho congelado.

## Execução e artefatos

Use os [comandos oficiais de predição](../../../script/README.md#4-predição).
O [guia do módulo](../../../src/prediction/README.md) detalha entradas e execução.

Nos splits científicos, o CSV requer `video_id`, `frame_index`, `annotated`,
`track_id`, `cx` e `cy`. O estado `annotated` propagado pelo tracking é
triestado: `1` é anotado, `0` é uma lacuna confirmada e vazio é desconhecido.
Somente `1` entra em uma janela. Portanto, ainda que existam posições
automáticas contínuas, nenhuma janela atravessa 823–972 ou 1084–1107 do vídeo
23. CSV legado sem essa coluna falha explicitamente em treino, validação, teste
e folds.

Em `split=application`, os 65 vídeos sem tracking manual podem omitir essa
coluna; a run então registra `annotation_policy=unavailable_application`. Isso
autoriza usar a trajetória observável para aplicação, sem apresentá-la como
ground truth ou validação quantitativa.

Métodos `flow_aware_*` também exigem `flow_u` e `flow_v`, interpretados como
movimento ambiental do frame da linha para o seguinte. `--track-id` pode ser
repetido. Por padrão, linhas do tracker com `predicted=1` são excluídas e suas
ausências viram lacunas; nenhuma janela atravessa essas lacunas.

O artefato compatível é criado pelo
[executor de integração](../../../script/README.md#3-movimento-aparente-por-fluxo),
usando o `cache_index.csv` da run de fluxo. Quando as células foram mascaradas, use a
amostragem `background` em anel; `direct` é o controle sem exclusão no centro.
Vetores ausentes permanecem inválidos e não são convertidos em zero.

`--history-length`, `--horizons` e `--stride` controlam as janelas. A previsão
com fluxo usa operacionalmente o último fluxo observado. O modo
`--set data.future_flow_mode=observed` é apenas uma análise controlada/oráculo e
fica registrado na run. A LSTM com fluxo usa somente atributos históricos e
registra `historical_features_only`; ela nunca recebe o fluxo futuro.

Cada execução cria uma pasta nova em
`data/tests/prediction/<algoritmo>/<configuração>/<etapa>/<run_id>/`; somente
teste/OOF/aplicação congelados seguem para `data/results/`, contendo:

- `predictions.csv`: previsão, alvo e erro para cada janela/horizonte;
- `window_metrics.csv`: ADE, FDE e erro por horizonte em cada janela;
- `summary.json` e `summary.csv`: agregados, custo e recursos;
- `metadata.json` e `manifest.json`: hash do CSV, filtros, configuração, seed e
  proveniência.

LSTM nunca é ajustada implicitamente sobre o CSV avaliado. Escolha exatamente
um modo: inferência com checkpoint ou treino explícito em um CSV de vídeos
disjuntos. Consulte os
[comandos oficiais de predição](../../../script/README.md#4-predição).

A CLI rejeita sobreposição de IDs de vídeo entre treino e avaliação. O mesmo
bloqueio de protocolo impede busca ou avaliação prematura no split de teste.
