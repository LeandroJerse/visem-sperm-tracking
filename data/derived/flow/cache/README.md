# Cache de movimento aparente

Campos `.npz` recriáveis gerados por
`python -m script.flow.test.run_flow`. A chave
inclui vídeo, par de frames, configuração, método e, quando usada, a máscara de
boxes. O `cache_index.csv` da run é o catálogo que deve ser passado ao tracking
híbrido ou ao enriquecimento de trajetórias.

Não reutilize um campo se vídeo, parâmetros ou política de máscara mudarem.
