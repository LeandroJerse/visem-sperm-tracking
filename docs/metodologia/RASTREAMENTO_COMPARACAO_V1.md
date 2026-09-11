# Comparação prospectiva de rastreamento — v1

Data: 11/09/2026. Estado: **contrato em preparação; bateria real não liberada**.
Plano associado: [`comparison_v1.yaml`](../../configs/tracking/comparison_v1.yaml).
Este documento inicia a frente de rastreamento do
[plano executivo](CONTINUIDADE_EXPERIMENTAL_V1.md). Não contém resultados,
seleção, promoção ou autorização de abertura do teste. O YAML é uma especificação
de desenho; a CLI atual não implementa seus bloqueios nem seu avaliador.

## 1. Perguntas e ordem dos experimentos

A pergunta desta frente é: mantendo as detecções fixas, qual método preserva
melhor as identidades e produz trajetórias úteis para a predição? A comparação
de detector+rastreador é posterior e considera também as falhas da detecção.
Um bom F1 de detecção não assegura boas identidades ao longo do tempo.

| Braço | Entrada | O que permite investigar | Limitação |
|---|---|---|---|
| Diagnóstico GT | Caixas individuais 0/2, sem IDs e sem classe morfológica | Associação com localização anotada | Não mede detecção; confiança constante não testa recuperação de baixa confiança |
| T218 | Todas as detecções brutas do threshold congelado para desenvolvimento | Associação com falsos positivos, perdas e caixas automáticas | Não representa detector aprendido nem teste confirmatório |
| YOLO | Detecções e scores reais de modelo treinado no protocolo próprio | Efeito do detector e associação em duas faixas de confiança | Depende de ambiente, treinamento e contrato de detecção |
| Fluxo na associação | Mesmas detecções do braço correspondente + campos causais | Contribuição do fluxo ao rastreamento | Requer campos em posições estimadas, diferentes das amostras GT de predição |

Começar com centroide, Húngaro e SORT no diagnóstico, após liberar o contrato.
Incluir ByteTrack-style nesse diagnóstico como controle de implementação;
sua comparação principal deve incluir YOLO. Depois repetir com T218. O
Adaptive Flow-SORT será comparado com sua própria variante `flow_weight=0`
e com SORT: o contraste com SORT sozinho também muda a associação e não
isola o efeito do fluxo. Nenhum vencedor será escolhido pelo smoke.

## 2. Implementações locais e parâmetros

Os nomes abaixo correspondem a `src/tracking/factory.py`, não a wrappers
automaticamente equivalentes a repositórios externos.

| Nome estável | Código | Decisão de associação |
|---|---|---|
| `centroid_greedy` | `src/tracking/classical/centroid.py` | Associação gulosa por centros |
| `hungarian` | `src/tracking/classical/hungarian.py` | Custo global por centros |
| `sort` | `src/tracking/classical/sort.py` | Kalman local e IoU |
| `bytetrack_style` | `src/tracking/modern/bytetrack_style.py` | Duas etapas por confiança; implementação local |
| `adaptive_flow_sort` | `src/tracking/hybrid/adaptive_flow_sort.py` | Kalman, fluxo local e combinação distância/IoU |

A variante ByteTrack-style não é reprodução integral do
[ByteTrack oficial](https://github.com/FoundationVision/ByteTrack), distinção
já estabelecida no plano executivo. GT e threshold têm scores constantes;
não alterar artificialmente seus scores para produzir uma vantagem aparente.

O YAML fixa configurações de **smoke**, extraídas das configurações locais já
existentes, sem busca. Não são finalistas. As grades históricas `search.yaml`
continuam preservadas e não são executadas por este plano. Uma busca posterior
terá candidatos, orçamento amostral, critério de seleção, desempates e
validação registrados antes de observar resultados.

No primeiro smoke todos usam `class_aware=false`, `min_hits=1` e
`emit_predictions=false`. Isso fixa quais saídas existem; os estados internos
perdidos ainda podem participar de associações posteriores. Uma avaliação
futura que emita caixas Kalman sem detecção será outro braço explícito, com
FP/FN e cobertura correspondentes. Não misturar as duas políticas num ranking.

## 3. Entradas, classes e independência do rastreador

Somente os 12 treinos são elegíveis: 11, 12, 13, 15, 21, 22, 23, 29, 30, 35,
60 e 82. O primeiro smoke prospectivo usa 0..19 dos vídeos 11/12. Ele é um
novo experimento de tracking e não uma repetição do smoke de fluxo.
Após conferência, o diagnóstico ampliado pode cobrir todos os quadros dos
12 treinos, em plano de execução próprio. Validação, teste, folds e `all`
ficam bloqueados nesta especificação.

O leitor deve autenticar manifesto, QA, tabelas e contagens da referência
individual do nível 5. Esse derivado preserva coordenadas, classes, IDs e
segmentos; não é necessário repetir sua preparação. A política espacial
depende também das caixas de cluster preservadas nesse conjunto. Os 174
quadros sem anotação do vídeo 23 devem ser mantidos como tais.

No diagnóstico, construir um novo objeto de entrada contendo somente
`cx,cy,w,h,score=1,class_id=0,object_id=None`. Filtrar a referência pelas
classes 0/2 exclusivamente para construir esse cenário ideal. Remover o ID
antes da chamada, ordenar por geometria e nunca pelo ID manual. Preservar as
classes e IDs originais em outro canal acessível somente ao avaliador.
Testes devem trocar IDs e ordem das anotações sem criar acesso do rastreador
ao gabarito. Empates geométricos precisam de ordenação determinística documentada.

Na execução com detector, todas as previsões brutas entram no rastreador,
independentemente da classe prevista. Não remover regiões, trajetórias ou
detecções usando máscaras, IDs ou pareamentos GT. O filtro de avaliação de
clusters atua **depois** do rastreamento, sem corrigir seu estado ou suas saídas.
A classificação morfológica é complementar, não um mecanismo para evitar FP.

GT das classes 0/2 representa indivíduos. A mudança 0↔2 não cria outro ID.
Classe 1 não representa um indivíduo e nunca vira sua posição ou seu ID.
Dentro de cada bloco anotado, o ID original individual é preservado mesmo
quando reaparece após uma ausência de observação individual; o avaliador
mede a associação entre suas observações individuais disponíveis. O trecho
sem observação individual não recebe caixa interpolada nem FN daquele ID.
É diferente do corte em segmentos necessário para janelas densas de predição.
Não inferir que um cluster contém um indivíduo específico sem anotação disso.

## 4. Tempo, lacunas e quadros vazios

O universo temporal deve vir de uma tabela autenticada de status por quadro,
com `annotated=true/false`. A ausência de uma linha longa de objeto não basta.
Status desconhecido, duplicado ou contraditório bloqueia o experimento.
Não usar o fallback por linhas manuais da CLI histórica nesta bateria.

Na pipeline automática, chamar o rastreador em **todos** os quadros do vídeo,
inclusive com uma lista de detecções vazia, e preservar saídas nas lacunas.
Não resetar o método por causa do conhecimento de uma lacuna GT. O algoritmo
continua recebendo apenas informação causal das imagens e detecções.

Para avaliação propõe-se dividir cada vídeo em seus blocos máximos de quadros
consecutivos anotados. Os blocos serão sequências de avaliação separadas,
sem concatenar imagens separadas por lacunas. Não haverá penalidade de
identidade ou alegação de reencontro através de um intervalo não avaliável.
Esta restrição temporal precisa constar no nome do protocolo e nas tabelas.
No diagnóstico ideal, que não possui caixas nas lacunas, reiniciar em cada
bloco; isso não será apresentado como desempenho da pipeline automática.

Quadro anotado vazio permanece dentro do bloco: cada previsão avaliada nesse
quadro pode contribuir como FP. Retirar um bloco inteiro porque um método
não produziu previsões é proibido. Os blocos do mesmo vídeo não são réplicas;
devem ser reunidos antes de resumir os vídeos. O smoke confirmará essa regra
com fixtures de lacunas mesmo que seus dois prefixos reais não as contenham.

## 5. HOTA, identidade e geometria

Usar as classes de métricas do TrackEval, mantendo sua implementação
inalterada e fixando o commit externo antes da execução. HOTA equilibra
detecção e associação, incorporando localização por limiares de similaridade;
seus componentes devem ser mostrados junto ao número principal.
[Artigo HOTA](https://arxiv.org/abs/2009.07736).

Para caixas, a similaridade será IoU contínua entre retângulos, sem `+1` na
largura/altura da interseção. HOTA será a média de seus 19 limiares
0,05..0,95, com DetA, AssA e LocA. Não haverá conversão para uma métrica
chamada “HOTA a 10 px”. [Implementação HOTA](https://github.com/JonathonLuiten/TrackEval/blob/master/trackeval/metrics/hota.py).

IDF1/IDP/IDR virão de Identity com similaridade mínima 0,5. MOTA, IDSW,
fragmentações e contagens CLEAR usarão o limiar 0,5 do respectivo módulo.
Manter a configuração explícita, inclusive os defaults. Os diagnósticos
locais por centros continuam separados e não são substitutos dessas métricas.
[Identity](https://github.com/JonathonLuiten/TrackEval/blob/master/trackeval/metrics/identity.py),
[CLEAR](https://github.com/JonathonLuiten/TrackEval/blob/master/trackeval/metrics/clear.py).

Caixas pequenas podem ter boa proximidade de centro e IoU baixo. Apresentar
conjuntamente métricas de localização por centros e HOTA-IoU, explicando que
medem propriedades distintas. Não aumentar caixas ou mudar o limiar após
observar qual rastreador ganha.

O formato MOT usa frames/IDs e origem de caixa em base 1. Nosso CSV analítico
fica em base 0 e coordenadas contínuas originais. Para um bloco iniciado no
quadro `b`, exportar `frame_mot=frame_original-b+1`, `x_mot=cx-w/2+1` e
`y_mot=cy-h/2+1`, preservando `w,h`. Aplicar exatamente a mesma translação ao
GT e às previsões, sem clipping nem arredondamento a inteiros. O mapeamento
reversível dos IDs inteiros positivos fica num arquivo separado.
[Formato oficial](https://github.com/JonathonLuiten/TrackEval/blob/master/docs/MOTChallenge-Official/Readme.md).

GT MOT terá campos `frame,id,x,y,w,h,mark=1,class=1,visibility=1` para os
indivíduos avaliáveis. A classe 1 desse adaptador é um código de intercâmbio,
sem relação com classe 1/cluster do VISEM. Tracker terá as dez colunas MOT,
com score original e campos finais -1. Usar serialização que reconstrua
`float64` (`.17g` ou equivalente) e conferir round-trip. O exportador atual
arredonda seis casas e adiciona somente o offset de frame; ele não será
usado como prova desta convenção nova sem adaptação e teste.

## 6. Clusters: decisão ainda aberta antes da bateria

A implementação `MotChallenge2DBox` faz pré-processamento de distractors
por associação IoU 0,5; não implementa regiões crowd arbitrárias. Desligar
`DO_PREPROC` evita importar essa regra indevidamente, mas não resolve a
avaliação de clusters do VISEM. A ferramenta recomenda explicitar esse
pré-processamento ao converter datasets próprios.
[Código do dataset](https://github.com/JonathonLuiten/TrackEval/blob/master/trackeval/datasets/mot_challenge_2d_box.py),
[documentação de datasets próprios](https://github.com/JonathonLuiten/TrackEval#evaluate-on-your-own-custom-benchmark).

Não exportar clusters simplesmente como distractors MOT: uma caixa grande
e diversas cabeças não correspondem a uma associação um-para-um. Também não
reaproveitar previsões ignoradas pelo matching de centros a 10 px para HOTA:
o pareamento temporal e os limiares IoU são diferentes. Isso poderia retirar
uma previsão elegível em algum limiar ou favorecer um método por um filtro
que depende de outro matching.

Duas análises possíveis precisam ser definidas e verificadas antes da run:

- **Conservadora:** manter todas as previsões contra GT individual. É
  reproduzível, mas pode penalizar células visíveis de clusters sem rótulo
  individual; deve ser identificada como análise de sensibilidade.
- **Com regiões ignoradas próprias:** remover somente previsões sem
  compatibilidade com qualquer indivíduo e cujo centro cai num cluster,
  preservando indivíduos dentro de clusters e duplicatas elegíveis. Exige
  especificar a compatibilidade (por exemplo, proteção que abranja todos os
  limiares HOTA), a dependência ou não de alpha, limites de caixa e os
  contadores de exclusão. Não será intitulada regra oficial VISEM/MOT.

A recomendação é investigar a segunda regra com fixtures, acompanhada da
análise conservadora, e só então fixar a versão prospectiva. **Neste v1 o
campo `cluster_policy` é nulo e a execução está desativada.** A decisão não
deve ser escolhida por produzir maior HOTA real. O status impede que uma
adaptação ainda não definida seja confundida com avaliação pronta.

## 7. Fluxo no rastreamento

Na chamada do quadro `t`, só pode entrar o par `t-1→t`, disponível após a
leitura do quadro atual. O primeiro quadro após reset não tem esse campo.
O campo deve estar vinculado por hash ao vídeo, par, geometria, configuração,
validade e completude. Não usar o par `t→t+1`, nem vetores dos alvos futuros.

As 15.762 amostras do nível 8a estão em centros GT específicos. Um rastreador
amostra posições estimadas diferentes; os 24 pares densos sentinelas não
constituem o cache de todos os quadros. Esse derivado não libera Adaptive
Flow-SORT automaticamente. Será necessário contrato e extração próprios.

A revisão encontrou três limitações no consumidor legado:

1. `LazyFlowCacheIndex` identifica par/caminho, mas não obriga vídeo e hashes
   por campo; uma falta posterior produz `None`, em vez de falhar a bateria.
2. `sample_flow` transforma amostra fora da imagem, sem vetores válidos ou
   não finita em `(0,0)`. Isso não pode ser registrado como movimento medido.
3. O método atual soma fluxo à caixa já extrapolada pelo Kalman e amostra
   nessa caixa. Isso é uma heurística local, pode somar movimento duas vezes
   e não equivale a advecção amostrada na origem do campo.

Antes do braço com fluxo, registrar qual comportamento se quer comparar,
preservando a variante legada e dando outro nome a mudanças científicas.
Representar validade separadamente; um fallback para Kalman, se adotado,
deve ser explícito, contado e comparado com o controle sem fluxo. Não
afirmar que amostragem inválida é velocidade zero nem velocidade do fluido.

## 8. Agregação, seleção posterior e predição real

Calcular por bloco com TrackEval e reunir os blocos do mesmo vídeo pelos
combinadores da métrica, preservando estatísticas suficientes, em vez de
tirar média simples dos HOTAs dos blocos. A implementação dessa agregação
também precisa de fixtures. Depois dar peso igual a cada vídeo na síntese
principal; publicar também cada vídeo, dispersão, detecções, IDs, tempo,
RAM e cobertura. O agregado padrão de todos os blocos não substitui a
análise pareada por vídeo. Escala de armazenamento e apresentação de
porcentagens precisa ser explícita e conferida.

O smoke não faz seleção. Antes da busca, registrar HOTA macro por vídeo
como critério principal e critérios objetivos para desempates, falhas e
custo. Validar candidatos escolhidos no treino em vídeos completos de
validação; congelar configurações identificadas antes de avaliação externa.
Não combinar rankings de diagnóstico GT e pipeline automática como se
fossem a mesma tarefa. A exposição histórica do teste continua declarada.

Após comparar e validar detectores/rastreadores, avaliar combinações
selecionadas com predição em trajetórias estimadas. Preservar seus IDs,
trocas, falhas e gaps reais; um GT não pode reconstruir o histórico que o
sistema perdeu. A correspondência entre trajetórias estimadas e alvos
manuais pertence somente ao avaliador e terá contrato próprio. Reportar
ADE/FDE e cobertura conjunta: minimizar erro descartando os casos difíceis
não comprova melhor funcionamento. O melhor detector isolado não é
automaticamente a melhor combinação para trajetórias futuras.

## 9. Entregas e condições para liberar dados

Antes de executar, são necessários:

1. Versão/commit fixado de TrackEval, ambiente mínimo e testes sintéticos
   de HOTA/Identity/CLEAR com resultados conhecidos, sem remendo silencioso.
2. Política de clusters decidida com fixtures; dataset/exportador que
   preserve indivíduos, lacunas, vazios, coordenadas e IDs sem vazamento.
3. Leitor autenticado da referência e detecções; manifesto completo de
   frames; projeção de memória/armazenamento; limites explícitos por run.
4. Executor que recuse status de rascunho, dados fora do treino, entradas
   incompletas, GT no canal de associação e alterações científicas por CLI.
5. CSV/MOT por método e vídeo, mapas de frames/IDs, exclusões, outputs
   TrackEval brutos, tabela por vídeo, configuração resolvida e proveniência.
6. Conferência independente de cobertura, associações sintéticas, round-trip,
   diferenças numéricas e contagens; visualização curta com caixas e IDs.

Tempo será monitorado sem corte de 120 minutos. Memória, armazenamento e
completude continuam sendo condições de execução válida. O manifesto deve
registrar configuração, seed, commit/Git, dependências, hardware, recursos,
hashes de entradas/saídas e conclusão ou falha. Fontes e runs anteriores
permanecem imutáveis. Nenhuma falha parcial vira resultado completo.
