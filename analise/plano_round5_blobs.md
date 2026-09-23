# Blobs — plano do round5

**Rodada executada pelo pesquisador, concluída e conferida.** A
[análise do round5](analise_round5_blobs.md) e o
[documento completo de blobs](desenvolvimento_blobs.html) apresentam os resultados.
O texto abaixo preserva o planejamento anterior à execução.
Este plano segue a [análise do round4](analise_round4_blobs.md) e suas
[estatísticas](estatisticas_round4_blobs.json). Não há resultados do round5 ainda.

São **14 configurações × 178 quadros = 2.492 avaliações**: quatro controles
repetidos e dez configurações novas. O conjunto passa de 109 para **119
configurações distintas planejadas**, dentro do teto de 122. As cinco rodadas
somam 136 posições de configuração; não é necessário preencher o teto de distintas.

## Hipóteses e configurações

| Método | Variação | Quantidade | Objetivo |
|---|---|---:|---|
| SimpleBlobDetector (SBD) | Área mínima 56/64/72 × margem 2/3 | 6 | Refinar conjuntamente filtro de área e caixa |
| DoG | Resposta 0,10/0,12/0,14 × margem 5/6 | 6 | Investigar a região intermediária de sensibilidade e caixa |
| LoG | Limite de aglomerado equivalente a diâmetro 24/28; resposta 0,12 e margem 6 | 2 | Medir separadamente o efeito da classificação entre grupos |

As grades SBD e DoG combinam todos os valores dos dois fatores. O par LoG
muda somente um limite de classificação. Não foram acrescentados métodos,
pré-processamentos, escalas ou novas regras de avaliação.

| ID | Método | Área mínima / resposta | Margem (px) | Diâmetro mínimo equivalente para aglomerado (px) | Controle do round4 |
|---|---|---:|---:|---:|---|
| r5c01 | SBD | 56 | 2 | 24 | — |
| r5c02 | SBD | 56 | 3 | 24 | — |
| r5c03 | SBD | 64 | 2 | 24 | r4c03 |
| r5c04 | SBD | 64 | 3 | 24 | r4c04 |
| r5c05 | SBD | 72 | 2 | 24 | — |
| r5c06 | SBD | 72 | 3 | 24 | — |
| r5c07 | DoG | 0,10 | 5 | 24 | — |
| r5c08 | DoG | 0,10 | 6 | 24 | — |
| r5c09 | DoG | 0,12 | 5 | 24 | — |
| r5c10 | DoG | 0,12 | 6 | 24 | r4c07 |
| r5c11 | DoG | 0,14 | 5 | 24 | — |
| r5c12 | DoG | 0,14 | 6 | 24 | — |
| r5c13 | LoG | 0,12 | 6 | 24 | r4c18 |
| r5c14 | LoG | 0,12 | 6 | 28 | — |

O diâmetro da tabela é uma forma de explicar o corte. O parâmetro efetivamente
armazenado é `classificacao.area_minima_aglomerado`, calculado como π × (d/2)²
sobre a área circular estimada do blob. Não é a área da caixa adaptada nem
uma área segmentada. No SBD, o filtro `area_minima` da terceira coluna
pertence à seleção interna de candidatos do OpenCV; é um parâmetro distinto.

### SBD: interpolar onde houve interação

O melhor resultado continua r4c04, área 64/margem 3, F1 0,567571.
Área 80/margem 2 chegou a 0,566181: retirou 139 falsas detecções, mas perdeu
62 acertos. A diferença não foi consistente entre vídeos: cinco melhoraram
e sete pioraram, com intervalo exploratório de ΔF1 [−0,039690; +0,041472].

O efeito da margem depende da área. No round4, a diferença entre os efeitos
da margem nas áreas 80 e 64 foi −0,018366, com intervalo exploratório
[−0,031767; −0,004477]. Por isso, não escolher cada parâmetro isoladamente:
56 e 72 interpolam os intervalos 48–64 e 64–80, cruzados com as duas margens.
Os dois controles em área 64 permitem conferir a reprodução e comparar
o efeito da área em cada margem. Os melhores resultados históricos das
outras áreas continuam disponíveis, mesmo sem serem repetidos nesta grade.

Demais parâmetros da referência r4c04: polaridade clara, limiares 80–220
(máximo exclusivo), passo 5, repetibilidade 2, distância mínima 6, área
máxima 500, inércia mínima 0,4, circularidade e convexidade desligadas,
sem pré-processamento. Pequeno ≤π×3² e aglomerado ≥π×12².

### DoG: explorar entre os valores já testados

Resposta 0,12/margem 6 permanece a melhor referência, com F1 0,544980.
Aumentar resposta para 0,16 eliminou 1.552 FP, mas também 719 TP; no vídeo
35, os acertos caíram de 189 para dois. Respostas 0,20 e 0,24 pioraram ainda
mais a cobertura. Margem 8 piorou o F1 agregado nos quatro limiares testados.

Testar 0,10 e 0,14 investiga o interior dos intervalos já observados,
sem continuar elevando o limiar. Margem 5 interpola entre 4 e 6, mantendo
6 como referência. Isso pode reduzir caixas excessivas, mas também prejudicar
as pequenas; o cruzamento completo mede esse compromisso. Não se presume
que a resposta mais seletiva ou a caixa menor sejam melhores.

DoG mantém polaridade clara, sem pré-processamento, sigma mínimo 2,
máximo solicitado 12, razão 1,6 e sobreposição 0,5. A grade efetiva mantém
sigmas 2/3,2/5,12/8,192. Pequeno ≤π×4² e aglomerado ≥π×12². Essa grade
não alcança o diâmetro 24; sua limitação para aglomerados permanece explícita.
O refinamento também não resolve, por definição, a baixa cobertura de pequenos.

### LoG: testar uma fronteira de classificação

No melhor LoG, r4c18, 167 anotações normais perdidas possuem alguma previsão
classificada como aglomerado cuja caixa alcança IoU ≥0,50. O diagnóstico
abaixo usa apenas registros já salvos; não houve reclassificação, novo
pareamento ou estimativa de F1 para a nova configuração.

| Diâmetro bruto da previsão | Previsões de aglomerado | FN normais com melhor caixa válida nessa faixa | Pares oficiais de aglomerados |
|---|---:|---:|---:|
| [24, 28) | 317 | 149 | 0 |
| [28, 32) | 76 | 14 | 9 |
| ≥32 | 91 | 4 | 5 |
| Total | 484 | 167 | 14 |

A coluna dos FN escolhe a maior IoU entre previsões de aglomerado para cada
anotação normal perdida. São 167 ocorrências e 166 candidatos distintos;
um candidato pode concorrer por mais de uma anotação. Centros, caixas e
diâmetros são os registros da execução, sem nova detecção.

Origem: configuração r4c18 do batch `batch__20260920T232838676095Z`, tabelas
`deteccoes.csv`, `anotacoes.csv`, `pares.csv` e avaliações dos 178 quadros.
Os hashes de cada arquivo estão no manifesto `execucao.json`, cujo SHA-256
é `bc68128b180e4415ce8e7ce2866005b1fe8664c72f1e594cab251bba3ca72a65`.
O plano arquivado tem SHA-256
`f5d69b234435e2dfa64e681dc44eaac651fcf7a4eb9667a21e03a46ad62e154e`.

Elevar o corte para 28 muda para normal 317 candidatos da primeira faixa.
Eles incluem as caixas associadas a 149 desses FN, mas também outros 168
candidatos. Portanto, não se trata de prever 149 acertos adicionais: pode
haver novos FP e competição entre pares. O corte 28 preserva os rótulos
dos 14 aglomerados já pareados; elevar para 32 mudaria nove deles. Isso
justifica testar apenas 28 neste orçamento. Preservar o rótulo não garante
preservar o pareamento ou o F1 de aglomerados após a execução.

Os 95 aglomerados perdidos não possuem nenhuma previsão, de qualquer classe,
com IoU ≥0,50. Alterar o corte não resolve essa ausência de caixas válidas.
A regra continua uma aproximação por tamanho, sem afirmar classificação
biológica correta. Trocas 0↔2 continuam registradas separadamente; trocas
indivíduo↔aglomerado afetam o F1, pois mudam o grupo de correspondência.

O novo corte é **π×14² = 615,7521601035994 px²**, ante π×12² =
452,3893421169302 px². Demais parâmetros permanecem exatamente os de r4c18:
resposta 0,12, margem 6, sigma 2–12 em dez escalas lineares, sobreposição
0,5, polaridade clara, sem pré-processamento e pequeno ≤π×4². O limite de
pequeno não muda. Candidatos brutos e caixas devem ser idênticos no par LoG;
somente as classes na faixa atingida devem mudar.

## Dados, reprodução e saídas

O [plano congelado](../scripts/blobs/rodadas/round5.json) registra todos os
parâmetros, identidades das quatro rodadas anteriores, hashes e ordem fixa.
A seed 42 permanece registrada; esta grade não faz sorteios nem adapta
parâmetros durante a execução. Reproduzir exige também manter as entradas,
o código e as versões registradas. Tempos podem variar entre execuções.

São os mesmos 178 JPEGs anotados dos vídeos 11, 12, 15, 19, 21, 22, 23,
30, 35, 36, 47 e 60; quadros 0–1400 a cada 100, com exclusão já aprovada
dos quadros 900 e 1100 do vídeo 23 por falta de anotação.

Na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round5 --conferir
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round5
```

O primeiro comando confere planos, entradas e dependências, sem detectar
nem criar resultados. O segundo executa a rodada. Não é necessário repetir
as anteriores. A saída fica em `resultados/frame-to-frame/blobs/round5/`,
com nova pasta por tentativa, configurações identificadas, PNGs comparativos,
CSV, previsões YOLO, ranking, origens e código arquivado. Cada tentativa
preserva as anteriores. O gerador `planejamento_round5.py` é interno;
o comando de execução continua sendo o mesmo.

O PDF automático mantém quatro páginas: F1/precisão/recall, cobertura e
classificação, resultados por vídeo e contrastes controlados. A última
página separa os **seis pares de margem** do **par de classificação LoG**;
não atribui toda diferença a mudanças de caixa.

## Como analisar quando o pesquisador executar

1. Conferir as 2.492 avaliações, hashes, quadros e quatro controles repetidos.
2. Confirmar candidatos e classes iguais nos pares de margem. No par LoG,
   confirmar geometria igual e classes alteradas apenas conforme o novo corte.
3. Agregar TP/FP/FN antes de calcular F1 de indivíduos, preservando IoU ≥0,50,
   pareamento um a um, classes 0/2 agrupadas e aglomerados separados. Mostrar
   cobertura de 0/2/1 e erros de classificação; casos sem GT nem previsão
   permanecem indefinidos. Empates exatos mantêm o mesmo posto.
4. Comparar área/resposta mantendo a margem fixa e investigar as interações.
   Para LoG, observar ganhos e perdas de indivíduos e de aglomerados juntos.
5. Usar diferenças pareadas por vídeo e o mesmo bootstrap exploratório:
   12 vídeos como blocos, 10.000 reamostragens, seed 42. Frames não são
   amostras independentes. Intervalos são condicionais a estes vídeos já
   examinados, sem correção pela busca adaptativa ou múltiplos contrastes.
6. Encerrar o balanço das cinco rodadas e produzir o documento completo de
   blobs, explicando decisões, hipóteses, mudanças, resultados e limitações.
   Só depois preparar a comparação em outras imagens e os testes em vídeo,
   com revisão conjunta das escolhas.

Esta rodada não seleciona finalistas. Os dados reservados para etapas
posteriores têm histórico de exposição em experimentos anteriores; não
devem ser descritos como um conjunto nunca visto. k-NN permanece na etapa híbrida.

## Arquivos da preparação

| Arquivo | Alteração |
|---|---|
| `scripts/blobs/planejamento_round5.py` e `rodadas/round5.json` | Novo desenho determinístico, controles e cadeia das quatro rodadas anteriores |
| `scripts/blobs/planejamento.py` | Leitura e validação do esquema v5 |
| `scripts/blobs/executar_rodada.py` | Conferência da origem round4 e inclusão do gerador v5 no código arquivado |
| `analise/relatorio_rodada_blobs.py` | PDF v5 com seis pares de margem e um de classificação |
| `scripts/testes/test_planejamento_round5_blobs.py` | Testes do desenho, controles, orçamento e reprodução |
| `scripts/testes/test_executar_round5_blobs.py` | Testes de integração, integridade e alteração isolada da classe LoG |
| `scripts/testes/test_relatorio_rodada_blobs.py` | Validação do desenho v5 e do PDF, preservando versões anteriores |

Os guias `README.md`, `scripts/README.md`, `scripts/blobs/README.md`,
`algoritmos/classicos/README.md`, `analise/README.md`, `analise/plano_blobs.md`
e `analise/estado_pesquisa.md` apontam para a etapa atual. A análise do round4
recebeu apenas uma nota de continuidade. Os planos e resultados anteriores
permanecem preservados; os detectores conservam a implementação usada no round4.

Passaram **137 testes distintos**: 67 dos planejadores, 42 dos executores
e 28 do relatório. Foram usados dados sintéticos para verificar a execução
e as quatro páginas do PDF. No par LoG, a classe mudou somente na faixa
esperada, preservando todos os outros campos de detecção e as coordenadas
YOLO. Esses testes verificam o funcionamento, não o desempenho na base.

A conferência real com `--rodada round5 --conferir` terminou com sucesso:
14 configurações, 178 quadros e 2.492 avaliações previstas. Nenhuma detecção
ou pasta de resultados do round5 foi produzida nessa conferência. O plano
foi regenerado de forma idêntica em Python 3.13.3; os quatro planos
anteriores conservaram seus hashes. SHA-256 do plano round5:
`bfd27624ff6f84bcd5e80c96195449b6762ecb74fc3c23b5c0478495b387032f`.
