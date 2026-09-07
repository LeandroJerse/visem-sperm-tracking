# Métricas, eventos e exportação

## Saída analítica

`export_tracks_csv` grava uma linha por track/frame com vídeo, frame, ID, caixa,
score, classe, idade, quantidade de hits, tempo desde a última observação,
estado e indicador de previsão. O arquivo não é sobrescrito sem
`overwrite=True`.

`export_motchallenge` produz as dez colunas esperadas pelo ecossistema MOT. O
frame interno é base zero e recebe `frame_offset=1` por padrão. Fixar na
configuração se caixas Kalman não observadas serão incluídas.

## Auditoria local

`evaluate_identity_events` faz matching Húngaro um-para-um por distância de
centro e retorna:

- matches, falsos positivos e falsos negativos;
- precision e recall espaciais;
- eventos de troca de ID com ID anterior e atual;
- fragmentações com frame e objeto afetado.

Uma fragmentação exige que o objeto GT esteja anotado, seja perdido em pelo
menos um frame anotado e volte a ser associado. A ausência deliberada de label
não é convertida em erro pelo helper; esses frames devem ser excluídos do mapa
de entrada.

O CSV longo de objetos sozinho não diferencia "frame anotado e vazio" de
"frame sem anotação". Por isso `run_tracking` autodetecta o `frame_metrics.csv`
irmão (ou aceita `--frame-metrics-csv`) e usa sua coluna `annotated` como
universo oficial. Assim, uma track prevista em um frame anotado vazio conta
como falso positivo, enquanto lacunas como as do vídeo 23 permanecem fora da
avaliação. Se o companion não existir, o fallback por linhas manuais é mantido
e identificado explicitamente no summary/metadata.

Esses contadores servem para depuração e rastreabilidade. Não equivalem a HOTA,
IDF1 ou MOTA completos.

## HOTA oficial

HOTA será calculado pelo projeto TrackEval externo. `TrackEvalHOTAAdapter`:

1. verifica a existência de `scripts/run_mot_challenge.py`;
2. constrói o comando explícito com `--METRICS HOTA`;
3. lê somente uma coluna `HOTA` realmente produzida no resumo.

Se o TrackEval não estiver instalado, o adaptador lança erro. Não existe
fallback interno que produza um número chamado HOTA.

Antes da bateria oficial, criar a estrutura MOTChallenge de GT e previsões,
verificar base de frames, coordenadas, sequências e frames excluídos, e comparar
manualmente uma sequência curta com as visualizações.
