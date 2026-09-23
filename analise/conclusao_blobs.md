# Conclusão dos experimentos de blobs

## Avaliação final conferida em 21/09/2026

O ciclo de blobs está concluído: diagnóstico, cinco rodadas, seleção das
119 configurações distintas em imagens, cinco finalistas em vídeos de seleção
e avaliação final das mesmas cinco configurações congeladas.
O [documento de desenvolvimento](desenvolvimento_blobs.html) registra as
hipóteses e decisões das rodadas; esta conclusão acrescenta o resultado final.

Foram processados integralmente os vídeos 14, 24, 38 e 82, com 5.910 quadros
por configuração: **29.550 avaliações e vinte vídeos comparativos**.
São ocorrências em quadros, não indivíduos únicos. Não houve rastreamento.

| Configuração | Método | F1 indivíduos | Precisão | Recall | TP | FP | FN |
|---|---|---:|---:|---:|---:|---:|---:|
| s103 | DoG, margem 8 | 0,656233 | 0,726099 | 0,598632 | 95.453 | 36.007 | 63.999 |
| s084 | SimpleBlob, margem 4 | 0,593003 | 0,642066 | 0,550906 | 87.843 | 48.970 | 71.609 |
| s082 | SimpleBlob, margem 4 | 0,592312 | 0,639090 | 0,551915 | 88.004 | 49.698 | 71.448 |
| s051 | SimpleBlob, margem 5 | 0,575060 | 0,585582 | 0,564910 | 90.076 | 63.747 | 69.376 |
| s052 | SimpleBlob, margem 6 | 0,489895 | 0,498859 | 0,481248 | 76.736 | 77.087 | 82.716 |

O maior F1 final foi de s103, mas s052 havia liderado a seleção em imagens
e vídeos. A inversão reforça a dependência da configuração em relação ao vídeo.
O ranking final é descritivo: não muda retrospectivamente as escolhas nem
autoriza recalibrar parâmetros com esses dados.

## Localização não resolve a classificação

As referências finais contêm 156.516 ocorrências normais, 2.936 pequenas e
6.601 aglomerados. O critério permanece F1 de localização para classes 0/2
juntas, IoU >= 0,50 e pareamento exclusivo; aglomerados são outro grupo.

- s103 localizou 95.453 normais, mas classificou **75.864 como pequenos**.
  A acurácia de classificação entre os pares encontrados foi 20,52%.
  Não localizou nenhum dos pequenos anotados, nem aglomerados.
- s082 e s084 classificaram corretamente os normais que localizaram, mas
  perderam todos os 2.936 pequenos. A acurácia condicional de 100% não significa
  que reconheçam as duas classes.
- s052 e s051 localizaram, respectivamente, 30 e 20 pequenos; todos foram
  classificados como normais. O maior F1 de aglomerados foi apenas 0,021741.

A hipótese de classe por área estimada permanece fraca. Melhorar a caixa
pode melhorar o IoU sem corrigir o candidato ou sua classe. k-NN continua
reservado para os híbridos; não foi incluído neste resultado clássico.

## Comparação descritiva com limiarização

Nos mesmos vídeos e critérios, os maiores F1 finais observados foram
0,656233 em blobs (s103) e 0,566796 em limiarização (s099/s101): diferença
de **0,089437**, ou 8,94 pontos percentuais. São máximos observados entre
cinco candidatas de cada método, não vencedores escolhidos antes do teste.

| Vídeo | Blobs s103 | Limiarização s099 |
|---|---:|---:|
| 14 | 0,472354 | 0,372133 |
| 24 | 0,740490 | 0,536123 |
| 38 | 0,700810 | 0,894497 |
| 82 | 0,509235 | 0,553413 |

Blobs melhora em dois vídeos e piora em dois nesta comparação. O agregado
é dominado pelas contagens, principalmente do vídeo 24; não é a média dos
quatro F1. Não se estabelece superioridade estatística com milhares de
quadros tratados como amostras independentes: quadros do mesmo vídeo são
correlacionados e há somente quatro vídeos finais. O histórico de exposição
anterior aos dados permanece uma limitação para todos os detectores.

## Integridade e fontes

Batch: `resultados/videos/blobs/final/batch__20260921T034832637647Z`.
A leitura do avaliador de relatório confirmou as 29.550 linhas por quadro,
vinte agregados por vídeo, cinco totais, ranking, configurações e referências.
Foram conferidos **149 hashes de saídas e 5.978 de origens**, sem divergências.
Os vinte MP4s possuem hashes íntegros e registros de decodificação completa
da execução. Nesta auditoria não se repetiu o detector nem a decodificação.
O pesquisador também confirmou a inspeção visual dos vídeos.

O PDF possui quatro páginas, 83 fontes conferidas, hash válido e cópias do
plano e manifesto iguais às do batch. As quatro páginas foram renderizadas
e inspecionadas. Quatro fontes da comparação com limiarização também tiveram
seus hashes conferidos. As tabelas arredondam somente para apresentação.

- [Dados extraídos e registro da conferência](estatisticas_final_blobs.json).
- [Resumo final](../resultados/videos/blobs/final/batch__20260921T034832637647Z/resumo_configuracoes.csv).
- [Resultados por vídeo](../resultados/videos/blobs/final/batch__20260921T034832637647Z/resumo_por_video.csv).
- [PDF final](../resultados/videos/blobs/final/batch__20260921T034832637647Z/relatorios/20260921T041718384503Z/relatorio.pdf).
- [Conclusão da limiarização](conclusao_limiarizacao.md).

## Continuidade

Inicia-se watershed pelo [plano de inspeção](plano_watershed.md). As métricas,
classes e anotações continuam iguais. Desempenho e parâmetros de watershed
serão examinados no desenvolvimento; os vídeos finais não serão usados
para escolher seus limites.
