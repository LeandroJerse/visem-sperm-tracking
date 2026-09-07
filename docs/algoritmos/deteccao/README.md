# Detecção — índice de comparação

[Catálogo](../README.md) · [Código e contratos](../../../src/detection/README.md) · [Parâmetros](../../../configs/detection/) · [Comandos oficiais](../../../script/README.md#1-detecção) · [Ensaios](../../../data/tests/detection/README.md) · [Resultados promovidos](../../../data/results/detection/README.md)

Os três modos de limiarização usam a mesma implementação-base, mas são tratados
como algoritmos experimentais separados porque escolhem o limiar de maneira
diferente. MOG2 e KNN também compartilham uma interface, porém mantêm estado e
hiperparâmetros distintos.

| Método | Família | Principal vantagem | Principal risco |
|---|---|---|---|
| [Threshold fixo](threshold_fixo.md) | clássico puro | rapidez e interpretação | mudança de iluminação |
| [Otsu](otsu.md) | clássico puro | limiar automático global | superdetecção quando histograma não é bimodal |
| [Threshold adaptativo](threshold_adaptativo.md) | clássico puro | iluminação não uniforme | ruído local e muitos falsos positivos |
| [Threshold híbrido](threshold_hibrido.md) | híbrido clássico | corrige fundo antes de segmentar | mais parâmetros e possível realce de detritos |
| [Blob](blob.md) | clássico puro | filtros geométricos explícitos | sensível a polaridade, escala e sobreposição |
| [MOG2](mog2.md) | clássico temporal | separa movimento de fundo estático | aquecimento, fantasmas e deriva |
| [KNN](knn.md) | clássico temporal | fundo flexível, não paramétrico | custo e forte dependência do histórico |
| [Watershed](watershed.md) | clássico puro | separa regiões encostadas | sementes instáveis e sobre/subsegmentação |
| [YOLO](yolo.md) | aprendido | aparência, classes e confiança | labels/GPU/treino e overfitting |

Métrica principal comum: F1 binário por vídeo, com matching Húngaro de centros e
gate de 15 px. O custo é medido junto; nenhuma variante híbrida ganha o nome do
baseline que estende.
