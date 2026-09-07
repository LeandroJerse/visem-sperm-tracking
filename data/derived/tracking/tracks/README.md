# Trajetórias derivadas

Cópias tabulares recriáveis de tracks escolhidas para alimentar fluxo e
predição. `tracks_with_flow.csv` deve ser produzido por
`python -m script.integration.application.enrich_tracks_with_flow`; o
`tracks.csv` original permanece na run em `data/tests/` ou `data/results/` e
nunca é sobrescrito.

Use subpastas ou nomes que incluam cenário, método, vídeo e run ID. Não misture
tracks GT, tracks do detector e seeds diferentes no mesmo arquivo.
