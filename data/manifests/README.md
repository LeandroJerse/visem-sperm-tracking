# Manifestos de dados

Os CSVs versionados descrevem os dados locais sem versionar os vídeos.
O manifesto não transforma clipes derivados em amostras independentes.

`visem_tracking.csv` registra split, fold, número de frames anotados e condição
das anotações. Caminhos absolutos não devem ser armazenados aqui.

`visem_videos.csv` mapeia os 85 vídeos originais e distingue os 20 usados para
desenvolvimento/validação dos 65 usados somente após o congelamento.

`annotation_gaps.csv` registra intervalos sem arquivo de label. Atualmente são
174 frames do vídeo 23 (`823–972` e `1084–1107`), sempre excluídos das métricas
e do treino.

`layout_20260829.csv` é o mapa auditável entre a árvore antiga e a atual.
Os inventários locais `inventory_before_layout_20260829.json` e
`inventory_after_layout_20260829.json` registram o momento da migração;
`inventory_final_20260829.json` descreve a árvore depois da limpeza,
documentação e validação final. Esses JSONs não são versionados.

## Referências históricas após a migração

Os JSONs científicos já produzidos, incluindo `manifest.json` e
`metadata.json` das runs históricas, permanecem imutáveis. Por isso, eles podem
conter referências válidas à época da execução, como `results/`, `data/raw/`,
`data/tracked/` ou outros nomes anteriores. Esses valores são evidência de
proveniência e não devem ser reescritos apenas para refletir o layout atual.

No momento da leitura, `src/core/relocation.py` consulta
`layout_20260829.csv` e traduz tanto movimentos exatos de arquivo quanto
movimentos de árvores pelo prefixo mais longo. Assim, o consumidor encontra o
artefato canônico sem alterar o JSON que documenta a execução original. Uma
referência que não exista diretamente nem possa ser resolvida por esse mapa
deve ser tratada como erro de auditoria, nunca corrigida silenciosamente.
