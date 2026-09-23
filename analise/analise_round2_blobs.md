# Blobs — análise do round2

20/09/2026. Análise dos resultados salvos, sem executar detectores novamente.
Batch: `resultados/frame-to-frame/blobs/round2/batch__20260920T203403161690Z`.

**Conclusão:** o melhor F1 subiu de 0,551828 para 0,556433, um ganho pequeno.
A redução da distância mínima apresentou melhora mais consistente entre
vídeos que o aumento da área mínima. CLAHE piorou as oito comparações
pareadas. LoG/DoG ainda tiveram desempenho baixo, mas seus resultados
identificam duas hipóteses testáveis: resposta pouco seletiva e caixas pequenas.

O próximo desenho está na [proposta do round3](proposta_round3_blobs.md).
A proposta foi posteriormente aprovada e congelada para execução; o documento
vinculado registra a preparação. Esta análise utiliza somente resultados do round2.

## 1. Integridade e reprodução

- 32 configurações × 178 quadros = **5.696 avaliações concluídas**.
- 41.489 hashes de saídas e 360 origens conferidos, sem divergências.
- 22 arquivos do código arquivado, ZIP e três planos de origem conferidos.
- Resumos completos: 32 configurações, 384 linhas por vídeo e 5.696 por quadro.
- PDF de quatro páginas concluído, com apontador e hashes válidos.

Os quatro controles reproduziram exatamente as métricas e detecções do round1:

| Round2 | Referência | Detecções idênticas | F1 de indivíduos |
|---|---|---:|---:|
| r2c01 | r1c29 | 4.474 | 0,551828 |
| r2c02 | r1c23 | 5.893 | 0,373375 |
| r2c03 | r1c26 | 2.294 | 0,343925 |
| r2c04 | r1c43 | 6.300 | 0,083752 |

São 712 avaliações iguais ao excluir identificação e tempos, 18.961 registros
iguais nos 37 campos anteriores e 2.848 arquivos de anotações, correspondências,
pendências e YOLO idênticos byte a byte. As entradas também são as mesmas.
Repetições demonstram reprodução computacional; não acrescentam novos vídeos
nem novas observações biológicas independentes.

## 2. Resultados principais

Cada configuração encontra as mesmas 3.464 anotações normais, 134 pequenas e
109 aglomeradas. São ocorrências em quadros, não indivíduos únicos.

| Configuração | Alteração ou método | F1 indivíduos | Precisão | Recall | Normais localizados | Pequenos localizados | Aglomerados localizados |
|---|---|---:|---:|---:|---:|---:|---:|
| r2c01 | Referência r1c29 | 0,551828 | 0,503554 | 0,610339 | 2.194 | 2 | 0 |
| r2c11 | Área mínima 48 | **0,556433** | 0,528222 | 0,587827 | 2.113 | 2 | 0 |
| r2c14 | Distância mínima 6 | 0,555359 | 0,509272 | 0,610617 | 2.195 | 2 | 0 |
| r2c06 | Margem 3 | 0,544038 | 0,496446 | 0,601723 | 2.163 | 2 | 0 |
| r2c17 | Referência + CLAHE 1 | 0,479396 | 0,399260 | 0,599778 | 2.157 | 1 | 0 |
| r2c28 | Melhor LoG | 0,086331 | 0,049137 | 0,355197 | 1.278 | 0 | 9 |
| r2c32 | Melhor DoG | 0,090275 | 0,055830 | 0,235686 | 845 | 3 | 0 |

A r2c11 retirou 276 FP em relação à referência, mas também perdeu 81 TP:
TP 2.196→2.115; FP 2.165→1.889. Seu F1 cresce pelo equilíbrio entre precisão
e recall, não por encontrar mais indivíduos.

A r2c14 retirou 48 FP e acrescentou um TP: TP 2.196→2.197;
FP 2.165→2.117. É um efeito menor, porém sem queda do F1 em nenhum dos
12 vídeos. Isso favorece testar a interação entre distância e área, em vez
de assumir que basta adotar todos os parâmetros da configuração de maior F1.

## 3. Modelo estatístico usado

Foi mantido o avaliador acordado: indivíduos 0/2 juntos, aglomerados separados,
IoU≥0,50, correspondência exclusiva e F1 calculado após somar TP/FP/FN.
Os instrumentos seguintes são diagnósticos; não substituem o critério de seleção.

1. **Contrastes pareados:** comparar configurações que diferem em um fator,
   no mesmo vídeo, além de comparar as contagens agregadas.
2. **Consistência entre vídeos:** contar vitórias, empates e derrotas e calcular
   a mediana das diferenças. Essa mediana não é o F1 oficial da configuração.
3. **Bootstrap pareado por vídeo:** reamostrar os 12 vídeos com reposição,
   mantendo todos os seus quadros anotados e o mesmo sorteio para cada
   configuração. Recalcular o F1 das contagens somadas a cada repetição.

Foram 10.000 reamostragens, `numpy.random.default_rng(42)`, vídeos em ordem
numérica e percentis 2,5 e 97,5 com interpolação linear. O intervalo usa a
diferença de F1 em cada reamostragem. Não foram sorteados frames isoladamente.
O bloco contém os JPEGs anotados disponíveis de cada vídeo, não todos os frames
dos vídeos completos. A [documentação do bootstrap pareado](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html)
explica o uso dos mesmos índices para preservar o pareamento.

| Comparação com r2c01 | Δ F1 agregado | Vídeos: melhora / empate / piora | Intervalo de 95% exploratório para Δ F1 |
|---|---:|---:|---|
| Área mínima 48 — r2c11 | +0,004604 | 8 / 0 / 4 | −0,020448 a +0,034656 |
| Distância 6 — r2c14 | +0,003531 | 8 / 4 / 0 | +0,001480 a +0,005889 |
| Margem 3 — r2c06 | −0,007790 | 5 / 0 / 7 | −0,046427 a +0,032359 |
| Margem 6 — r2c08 | −0,074130 | 3 / 0 / 9 | −0,129482 a −0,014102 |
| Inércia 0,2 — r2c12 | −0,037876 | 3 / 0 / 9 | −0,059490 a −0,012649 |
| Sem inércia — r2c13 | −0,113439 | 0 / 0 / 12 | −0,144659 a −0,076089 |

Entre r2c11 e r2c14, a diferença é apenas +0,001074, com intervalo de
−0,023205 a +0,030822. Não há base para anunciar superioridade geral da
r2c11 por essa diferença. A distância 6 é a hipótese de ajuste mais
consistente neste painel; a área 48 merece investigação de interação.

Esses intervalos são **exploratórios**: apenas 12 blocos, dados já utilizados
no desenvolvimento e comparações escolhidas durante uma busca adaptativa.
Não corrigem a seleção entre configurações, múltiplas comparações ou possível
dependência entre vídeos. Não demonstram eficácia em vídeos inéditos.
O risco de favorecer particularidades do conjunto durante seleção é discutido
por [Cawley e Talbot, 2010](https://www.jmlr.org/papers/v11/cawley10a.html).

Os [dados estatísticos completos](estatisticas_round2_blobs.json) incluem
32 configurações, 29 contrastes, diferenças nos 12 vídeos, contagens,
intervalos, versões, receita reproduzível e hashes de quatro fontes.
Neste painel todos os F1 e as 10.000 reamostragens de cada contraste estão
definidos; nenhum caso foi substituído por zero ou descartado.

## 4. O que aprendemos sobre cada alteração

### Área, distância e inércia

Reduzir a área mínima de 32 para 16 ou 8 aumentou a recuperação de normais,
mas elevou mais os FP e não recuperou pequenos adicionais: ambos continuaram
com 2/134. Aumentar para 48 melhorou precisão à custa de recall.
Não avançar apenas para filtros progressivamente mais restritivos: medir
área e distância conjuntamente, mantendo a cobertura por classe visível.

Remover a inércia piorou todos os vídeos. Mantê-la em 0,4 no próximo bloco
evita gastar orçamento repetindo relaxamentos já desfavoráveis. Margens 3 e
4 continuam uma faixa razoável para o SimpleBlobDetector; margens maiores
pioraram o resultado agregado, portanto não transferir diretamente a proposta
de caixas maiores de LoG/DoG para esse detector.

### CLAHE

As oito variantes pioraram o F1 agregado. Nas referências r1c29 e r1c23,
ambas as intensidades de CLAHE pioraram os 12 vídeos. Na referência r1c26,
cada variante perdeu em nove vídeos; na referência escura, em dez ou onze.

Em várias referências aumentaram os FP; na referência com circularidade,
também foram perdidos muitos TP apesar de menos FP. O resultado não pode ser
resumido como uma única causa de ruído. CLAHE redistribui as intensidades,
e os parâmetros subsequentes ficaram fixos neste teste pareado.

**Proposta: não incluir CLAHE no round3.** Isso evita investir mais orçamento
nessa frente agora; não prova que todo ajuste futuro de CLAHE será inferior.

### Resposta e caixas de LoG/DoG

Com margem 2, subir o limiar de resposta de 0,02 para 0,05 produziu:

| Detector | TP antes → depois | FP antes → depois | Leitura |
|---|---:|---:|---|
| LoG | 1.279 → 1.278 | 107.806 → 24.731 | Retirou 83.075 FP, perdendo um TP |
| DoG | 859 → 848 | 50.544 → 14.341 | Retirou 36.203 FP, perdendo 11 TP |

Isso sustenta explorar respostas mais restritivas. Não permite estimar
antecipadamente quantos acertos serão preservados em 0,08 ou 0,12.

Adicionar margem 2 melhorou LoG nos 12 vídeos e DoG em 11, com um empate.
Os candidatos brutos foram idênticos em todos os frames dos pares
r2c25/26, r2c27/28, r2c29/30 e r2c31/32. O efeito observado nessas comparações
decorre da transformação da caixa, preservando classes e medidas brutas.

## 5. Diagnóstico de candidatos, caixas e pequenos

As categorias abaixo são mutuamente exclusivas para os FN oficiais. Primeiro
se verifica candidato do grupo com IoU válido; depois centro do grupo dentro
da anotação; depois centros apenas do outro grupo; por último, ausência.
Centro dentro de caixa **não é novo acerto**: pode ser ruído, halo ou fragmento.

| Situação dos FN de indivíduos | SBD r2c11 | LoG r2c28 | DoG r2c32 |
|---|---:|---:|---:|
| Sem centro dentro da anotação nem candidato válido do grupo | 654 | 94 | 129 |
| Centro do grupo indivíduos, sem caixa válida | 768 | 2.000 | 2.605 |
| Centros somente do grupo aglomerado | 56 | 219 | 0 |
| Candidato válido perdido no pareamento exclusivo | 5 | 7 | 16 |
| **FN total** | **1.483** | **2.320** | **2.750** |

Centros fora de todas as anotações aparecem em 1.107/1.889 FP do SBD,
18.131/24.731 do LoG e 9.319/14.341 do DoG. Caixas maiores não eliminam
esse excesso de candidatos; por isso o próximo desenho também varia resposta.

Para os 134 pequenos, o diagnóstico é distinto:

- **SBD:** 128 sem centro, quatro com centro e caixa inválida, dois localizados
  como normal. Mudar só a caixa ou o rótulo não recupera os 128 sem candidato.
- **LoG:** 23 sem centro, 106 com centro do grupo indivíduos e caixa inválida,
  cinco com centros somente classificados como aglomerado. Dos 111 com centro,
  87 têm dois a seis centros; não afirmar que 111 cabeças foram encontradas.
- **DoG:** 70 sem centro, 61 com centro e caixa insuficiente, três localizados.

Entre os 106 pequenos LoG com centro do grupo indivíduos, a melhor caixa entre
esses centros tem IoU mediano 0,2589 e razão mediana área prevista/anotada
0,2908. **103/106 têm menos de metade da área anotada.** Em 93 casos o
melhor candidato usa sigma 2, resultando em caixa 10×10 com margem 2.

Exemplo: em `12_frame_200`, anotação pequena índice 30, a caixa real de
referência mede 17×17. O candidato em (33,339), quase centralizado, tem caixa
10×10 e IoU 0,3460. Aumentar a margem é uma hipótese concreta para essa
falha, a ser testada também contra o custo de incluir regiões indevidas.

As caixas anotadas dos pequenos têm largura mediana 19 e altura mediana
17 pixels; as dos normais, aproximadamente 21,15 e 21. Há sobreposição
importante de tamanhos. **A classe 2 não significa simplesmente uma caixa
minúscula**, e medidas do brilho estimado não equivalem à anatomia.

Os cinco pequenos LoG bloqueados pelo grupo são ocorrências nos frames
100–500 do vídeo 35, com GT 27×29 e IoUs entre 0,6042 e 0,7513, mas
previsão classe 1. Essa limitação de classificação por área deve ser preservada
no relato; não é resolvida pela regra que aceita trocas apenas entre 0 e 2.

## 6. Aglomerados e limites de escala

Os melhores SBD, LoG e DoG localizaram respectivamente 0, 9 e 0 das 109
anotações de aglomerados. Todos os nove acertos LoG usam sigma 12.

No DoG, a grade observada foi 2; 3,2; 5,12; 8,192. Com a classificação
definida por diâmetro ≥24, nenhuma dessas escalas pode produzir classe 1:
o maior diâmetro é aproximadamente 23,17. Portanto, a ausência de classe 1
tem uma restrição estrutural nessa configuração, além das dificuldades dos dados.
Ela não demonstra que o método DoG seja incapaz de detectar aglomerados.

A proposta do round3 mantém esse limite enquanto isola resposta e geometria,
priorizando indivíduos como acordado. Investigar sigma máximo maior e a
classificação de aglomerados permanece pendente; não apresentar os próximos
testes DoG como uma busca já completa nas três classes. A etapa híbrida com
k-NN continua futura, separada deste desenvolvimento clássico.

## 7. Próxima decisão

Recomenda-se um desenho fatorial explícito de 24 configurações, descrito na
[proposta do round3](proposta_round3_blobs.md). Ele testa interações entre
parâmetros em regiões justificadas pelos resultados, sem treinar outro modelo
para prever a configuração vencedora. Os 32 ensaios atuais são desbalanceados
entre famílias e compartilham dados; ajustar uma regressão ampla a todos eles
não forneceria uma previsão confiável de um ótimo global.

Nenhum detector, métrica, configuração executável ou resultado original foi
alterado nesta análise. Foram produzidos o relato, as estatísticas e a proposta;
as próximas execuções permanecem a cargo do pesquisador.
