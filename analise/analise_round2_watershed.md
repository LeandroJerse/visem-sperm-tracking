# Watershed — análise do round2

21/09/2026. Análise dos resultados salvos, sem executar novamente o detector.
Batch: `resultados/frame-to-frame/watershed/round2/batch__20260921T161513364669Z`.
As [estatísticas completas](estatisticas_round2_watershed.json) preservam
contagens, parâmetros, contrastes, hashes e diagnóstico das perdas.

**Conclusão:** execução íntegra e melhora no desenvolvimento. O maior F1
passou de 0,429887 para **0,466361**. A redução de falsas detecções compensou
a perda de alguns acertos. A localização ainda é limitada pelas regiões e
caixas produzidas; pequenos continuam pouco cobertos. As melhores configurações
estão próximas, portanto a primeira posição não define uma finalista.

## Conferência da execução

- **32 configurações × 178 quadros = 5.696 avaliações**, todas concluídas.
- 71.275 hashes de saídas e 3.209 de origens íntegros, sem divergências.
- **712 casos de controle**, com 2.848 arquivos de previsões, detecções,
  avaliações e diagnósticos idênticos ao round1.
- 29 fontes de código arquivadas e iguais às fontes atuais. Plano, origens,
  parâmetros e dependências registrados; arquivos originais preservados.
- Resumos completos: 32 configurações, 384 linhas por vídeo e 5.696 por quadro.
  Ranking e agregações conferidos; cada quadro tem os doze arquivos previstos.
- As 5.696 avaliações JSON reconciliam com as métricas tabulares. Os limiares,
  frações de máscara e contagens de pixels também foram conferidos.
- Os pareamentos dos 178 quadros da líder r2c10 foram recalculados a partir
  das caixas salvas e coincidiram integralmente com as avaliações.
- PDF de cinco páginas, hashes e 11.467 fontes conferidos; todas as páginas
  inspecionadas visualmente. Comparações examinadas: r2c10 em 30/0, 60/0,
  19/0 e r2c19 em 11/0.

A execução registrada durou **25 minutos e 37 segundos**, antes do PDF.
Nenhum resultado original, detector ou plano executável foi alterado nesta análise.

## Melhora e custo em acertos

Comparação nos mesmos 178 quadros, com as mesmas anotações e métricas:

| Configuração | F1 indivíduos | Precisão | Sensibilidade | TP | FP | FN | Pequenos localizados |
|---|---:|---:|---:|---:|---:|---:|---:|
| r1c11 = controle r2c01 | 0,429887 | 0,363811 | 0,525292 | 1.890 | 3.305 | 1.708 | 6/134 |
| **r2c10** | **0,466361** | **0,441520** | **0,494163** | **1.778** | **2.249** | **1.820** | **7/134** |
| r2c32 | 0,465718 | 0,439271 | 0,495553 | 1.783 | 2.276 | 1.815 | 10/134 |
| r2c11 | 0,465519 | 0,429951 | 0,507504 | 1.826 | 2.421 | 1.772 | 5/134 |
| r2c12 | 0,465471 | 0,434563 | 0,501112 | 1.803 | 2.346 | 1.795 | 5/134 |
| r2c15 | 0,465343 | 0,452800 | 0,478599 | 1.722 | 2.081 | 1.876 | 5/134 |

A líder usa Otsu sem deslocamento, área mínima **120**, semente **0,35**,
fechamento retangular **5×5** e preservação de aglomerados por área.
Comparada à líder anterior: **1.056 FP a menos, 112 TP a menos e +0,036473
em F1**. A melhora aparece em 11 dos 12 vídeos; no vídeo 36 há pequena
queda, de 0,575924 para 0,573150. O ganho do vídeo 60 é praticamente nulo.

Essa comparação muda área, semente e política ao mesmo tempo. Para entender
o efeito de cada parâmetro, usam-se os contrastes controlados abaixo.

## O que funcionou e o que não funcionou

### Área mínima

O ganho mais consistente continua vindo da rejeição de regiões pequenas.
Com semente 0,35 e preservação, aumentar mínimo de 48 para 96 retira
872 FP e 31 TP; o F1 melhora nos 12 vídeos. De 96 para 120, retira outros
291 FP e 46 TP, com melhora em dez vídeos.

Subir de **120 para 144 não melhora o F1 agregado** nas quatro combinações
de semente 0,35/0,75 e política separar/preservar. Na política da líder,
com semente 0,35, perde 101 TP e elimina 275 FP, reduzindo F1 a 0,462685.
Isso sustenta refinar a vizinhança de 120, sem simplesmente continuar
aumentando o filtro mínimo.

### Sementes e política de aglomerados

Com mínimo 120 e preservação, sementes 0,35, 0,50 e 0,75 resultam em F1
0,466361, 0,465718 e 0,465471. Separando regiões, 0,75 produz 0,465519.
As diferenças são pequenas e o efeito da semente depende da política.

No par r2c09 → r2c10, preservar elimina 170 FP, perde 25 TP individuais
e recupera nove aglomerados, aumentando F1 de indivíduos em 0,005235.
Esse resultado não demonstra superioridade universal da preservação.

A semente 0,15, testada com mínimo 48, não alcançou o grupo líder. A direção
mais baixa não merece prioridade sem outro diagnóstico que a sustente.

### Ajuste do limiar de Otsu

Nos contrastes com mínimo 120, semente 0,75 e fechamento 5×5:

| Deslocamento | F1 separar | F1 preservar | Fração média da máscara |
|---:|---:|---:|---:|
| -20 | 0,243680 | 0,243896 | 11,98% |
| -10 | 0,431870 | 0,425650 | 6,58% |
| **0** | **0,465519** | **0,465471** | **3,95%** |
| +10 | 0,375438 | 0,375202 | 2,10% |
| +20 | 0,226188 | 0,224870 | 1,54% |

Nenhum deslocamento testado superou zero no agregado. Reduzir demais o
limiar amplia a máscara e aumenta falsas detecções; elevá-lo perde muitos
acertos. A hipótese foi testada, mas não trouxe o ganho global esperado.

Existe heterogeneidade: **-10 melhora sete vídeos e piora cinco**, comparado
com zero. Em r2c19, o vídeo 11 cai 0,285713 em F1 e o vídeo 22 cai 0,261780;
o vídeo 60 melhora 0,227807. Portanto, não se deve afirmar que reduzir o
limiar sempre prejudica. Ajustes menores próximos de zero são uma hipótese
de refinamento, mantendo uma referência sem ajuste e os mesmos vídeos.

### Fechamento

Com os demais parâmetros fixos, **5×5 supera 3×3 e 7×7 no F1 agregado**
nas duas políticas. O fechamento 3×3 perde aproximadamente 175 TP; 7×7
perde de 24 a 33 TP e acrescenta FP.

O fechamento 7×7 localiza 13/134 pequenos, contra cinco nas referências
equivalentes de 5×5, mas perde no F1 principal. Esse resultado merece ficar
documentado como compromisso entre critérios, sem mudar a métrica acordada.

## Limitações que permanecem

### Localização e caixas

As caixas continuam no formato compatível com as anotações. Isso permite
compará-las; não garante que o contorno segmentado cubra a mesma região
que o anotador considerou.

Entre os **1.820 indivíduos perdidos por r2c10**, examinando todos os
candidatos salvos, inclusive os rejeitados:

| Diagnóstico | Quantidade |
|---|---:|
| Nenhum candidato chega a IoU 0,50, embora haja sobreposição | 1.650 |
| Candidato com IoU suficiente rejeitado pelo filtro de área | 83 |
| Nenhum candidato sobreposto | 69 |
| Candidato válido emitido no grupo de aglomerados | 11 |
| Candidato individual válido, mas sem par exclusivo disponível | 7 |

Essas categorias são mutuamente exclusivas; a prioridade e a definição
estão no JSON das estatísticas. Não são uma simulação de novos acertos.
Entre os candidatos de maior IoU dos FN com sobreposição, 677 têm caixa
menor que metade da área anotada e 596 têm pelo menos o dobro. Assim,
**expandir todas as caixas indiscriminadamente continua sem sustentação**.
São 1.180 perdas com melhor IoU entre 0,25 e 0,50: a geometria permanece
uma frente relevante além do filtro de área.

Visualmente, 30/0 apresenta boa correspondência, enquanto em 60/0 várias
caixas ficam menores que as anotadas. Em 19/0 há detecções excedentes e
perdas. A comparação de r2c19 em 11/0 mostra regiões ampliadas e fundidas.
Esses exemplos ilustram falhas diferentes; não substituem as métricas.

### Pequenos e classificação

A líder localiza **1.771/3.464 normais**, **7/134 pequenos** e **36/109
aglomerados**. Dos 127 pequenos perdidos, 63 não têm candidato sobreposto,
59 têm IoU insuficiente e cinco têm candidato válido rejeitado por área.

A acurácia condicional de 99,49% exige cuidado: **todos os sete pequenos
localizados foram classificados como normal**. Entre normais localizados,
1.769 foram classificados como normal e dois como pequeno. Com mínimo
120 e pequeno até 120, somente uma região de exatamente 120 pixels pode
receber classe 2. A maioria dos pares é de normais.

Sob a regra acordada, esses sete pequenos contam corretamente como acertos
de localização e erros de classificação. A acurácia alta não significa
boa identificação das duas classes, nem inclui os objetos perdidos.

## Estabilidade e próximo passo

A diferença entre primeira e segunda posições é apenas **0,000643**.
Retirar um vídeo por vez muda a líder: r2c10 permanece primeira em seis
retiradas; r2c11 e r2c15 em duas cada; r2c14 e r2c19 em uma cada.
Isso é um diagnóstico de sensibilidade, não validação cruzada nem teste
de significância. Os quadros de cada vídeo não são observações independentes.

Recomenda-se continuar com um round3 mais concentrado:

1. Refinar área mínima na vizinhança de 120, mantendo controles das líderes.
2. Preservar a comparação entre políticas e a faixa de sementes que se
   mostrou competitiva, sem considerar diferenças pequenas conclusivas.
3. Manter fechamento 5×5 como referência e investigar, se aprovado,
   deslocamentos menores de Otsu. Grandes deslocamentos tiveram custo alto.
4. Acompanhar perdas por geometria e cobertura de pequenos: aumentar o
   filtro de área sozinho não resolve a principal limitação observada.

**O round3 não foi preparado ou executado nesta etapa.** Seus parâmetros
devem ser definidos a partir deste diagnóstico. Não houve seleção de
finalistas nem consulta aos quadros reservados ou vídeos finais.
