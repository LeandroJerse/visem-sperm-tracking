# Detecção — índice de comparação

[Catálogo](../README.md) · [Código e contratos](../../../src/detection/README.md) · [Parâmetros](../../../configs/detection/) · [Comandos oficiais](../../../script/README.md#1-detecção) · [Ensaios](../../../data/tests/detection/README.md) · [Resultados promovidos](../../../data/results/detection/README.md)

Os três modos de limiarização usam a mesma implementação-base, mas são tratados
como algoritmos experimentais separados porque escolhem o limiar de maneira
diferente. MOG2 e KNN também compartilham uma interface, porém mantêm estado e
hiperparâmetros distintos.

Em 11/09 foi registrado o
[protocolo comparativo estático v1](../../metodologia/COMPARACAO_DETECTORES_CLASSICOS_V1.md)
para executar 43 configurações de threshold fixo, Otsu, adaptativo, híbrido,
Blob e Watershed na mesma amostra do treino. O protocolo distingue busca,
refinamento e validação; a shortlist inicial não é um vencedor final. YOLO
e métodos temporais precisam de seus próprios executores de dados/treinamento.

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

Nova avaliação: F1 por vídeo, com matching Húngaro de centros a 10 px e
sensibilidades de 15/20 px, conforme a
[decisão sobre tolerância](../../metodologia/TOLERANCIA_ESPACIAL.md).
A versão v3 avalia indivíduos 0/2, ignora previsões residuais em regiões
cluster somente sem indivíduo próximo e mantém avaliação complementar de
todos os objetos. Regra em [Classes e agrupamentos](../../metodologia/CLASSES_E_AGRUPAMENTOS.md).
As métricas já registradas a 15 px permanecem históricas. O custo é medido
junto; nenhuma variante híbrida ganha o nome do baseline que estende.
