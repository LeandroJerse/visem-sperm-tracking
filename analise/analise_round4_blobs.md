# Blobs — análise do round4

Continuidade: o [round5 foi preparado](plano_round5_blobs.md) após a revisão
desta análise. O texto abaixo preserva as conclusões registradas antes do novo plano.

20/09/2026. Análise das saídas salvas, sem executar detectores novamente.
Batch: `resultados/frame-to-frame/blobs/round4/batch__20260920T232838676095Z`.

**O round4 não aumentou o maior F1 observado.** A liderança continua em
0,567571, reproduzindo a configuração do round3. A melhor configuração nova
alcançou 0,566181: retirou falsos positivos, mas perdeu acertos. O experimento
delimitou regiões desfavoráveis, principalmente respostas altas e caixas
maiores no DoG. Não houve falha de execução que explicasse esses resultados.

O [plano executado](plano_round4_blobs.md) preserva as hipóteses formuladas
antes de observar a rodada. As [estatísticas completas](estatisticas_round4_blobs.json)
registram 18 configurações, cinco referências históricas, 42 contrastes,
contagens por vídeo, receita de reprodução e hashes das oito fontes.

## Integridade e reprodução

- **18 configurações × 178 quadros = 3.204 avaliações completas.**
- 22.535 hashes de saídas e 362 origens conferidos, sem divergências.
- ZIP íntegro com 24 arquivos de código e cinco planos de origem arquivados.
- Resumos validados: 18 configurações, 216 linhas por vídeo e 3.204 por quadro.
- PDF confirmado com quatro páginas; apontador e hashes válidos.

| Controle | Referência | F1 indivíduos |
|---|---|---:|
| r4c02 | r3c05 | 0,564380 |
| r4c04 | r3c09 | 0,567571 |
| r4c07 | r3c24 | 0,544980 |
| r4c16 | r3c16 | 0,285958 |
| r4c18 | r3c18 | 0,428430 |

Os cinco controles reproduziram exatamente 890 avaliações ao excluir IDs
e tempos, 34.635 registros de detecção e 4.450 arquivos de tabelas e YOLO
idênticos byte a byte. Entradas, dependências e código dos detectores
permaneceram iguais ao round3. Repetições verificam reprodução computacional,
não acrescentam amostras biológicas independentes.

## Resultados principais

Cada configuração utiliza 3.464 anotações normais, 134 pequenas e 109
aglomeradas. São ocorrências em quadros, não indivíduos únicos.

| Configuração | Método e parâmetros | F1 | Precisão | Recall | TP / FP / FN | Localizadas 0 / 2 / 1 |
|---|---|---:|---:|---:|---|---|
| r4c04 | SBD área 64/margem 3; controle | **0,567571** | 0,557162 | 0,578377 | 2.081 / 1.654 / 1.517 | 2.078 / 3 / 0 |
| r4c05 | SBD área 80/margem 2; melhor nova | 0,566181 | 0,571307 | 0,561145 | 2.019 / 1.515 / 1.579 | 2.017 / 2 / 0 |
| r4c07 | DoG resposta 0,12/margem 6; controle | 0,544980 | 0,460418 | 0,667593 | 2.402 / 2.815 / 1.196 | 2.402 / 0 / 0 |
| r4c09 | DoG resposta 0,16/margem 6 | 0,514364 | 0,571283 | 0,467760 | 1.683 / 1.263 / 1.915 | 1.683 / 0 / 0 |
| r4c18 | LoG resposta 0,12/margem 6; controle | 0,428430 | 0,317324 | 0,659255 | 2.372 / 5.103 / 1.226 | 2.367 / 5 / 14 |
| r4c16 | LoG resposta 0,08/margem 6; controle | 0,285958 | 0,183094 | 0,652585 | 2.348 / 10.476 / 1.250 | 2.331 / 17 / 25 |

As melhores configurações de cada método são controles. Isso não demonstra
que o ótimo foi encontrado, mas impede apresentar esta rodada como melhoria
do máximo. Houve ganhos em partes do painel, acompanhados de perdas em outras.

## Análise estatística

Mantidos indivíduos 0/2 juntos, aglomerados separados, IoU≥0,50, pareamento
exclusivo e F1 das contagens somadas. Classificação 0↔2 continua separada.

Bootstrap exploratório pareado por vídeo: 12 blocos, 10.000 reamostragens,
`numpy.random.default_rng(42)`, mesmos índices em todos os termos, percentis
2,5 e 97,5 com interpolação linear. Cada bloco reúne os JPEGs anotados de
um vídeo, não frames independentes. Vitórias, empates e derrotas usam frações
exatas de F1. Interações usam diferenças de diferenças na mesma reamostragem.

| Contraste | ΔF1 agregado | Melhora/empate/piora por vídeo | Intervalo 95% exploratório |
|---|---:|---|---|
| Melhor nova r4c05 − controle r4c04 | −0,001391 | 5/0/7 | −0,039690 a +0,041472 |
| SBD área 80 − área 64, margem 2 | +0,013610 | 8/0/4 | −0,001235 a +0,027471 |
| SBD margem 3 − margem 2, área 80 | −0,003365 | 7/0/5 | −0,057305 a +0,047295 |
| DoG margem 8 − margem 6, resposta 0,12 | −0,031764 | 4/0/8 | −0,081094 a +0,029115 |
| DoG resposta 0,16 − resposta 0,12, margem 6 | −0,030616 | 4/0/8 | −0,122552 a +0,043139 |
| DoG resposta 0,24 − resposta 0,12, margem 6 | −0,341495 | 0/0/12 | −0,442713 a −0,226605 |
| LoG margem 6 − margem 5, resposta 0,12 | +0,013185 | 6/1/5 | −0,009446 a +0,043993 |
| LoG resposta 0,12 − resposta 0,08, margem 6 | +0,142472 | 12/0/0 | +0,113874 a +0,169394 |

Os 42 contrastes tiveram 10.000 reamostragens definidas. Os intervalos são
exploratórios, condicionais aos 12 vídeos já reutilizados, e não corrigem a
busca adaptativa nem comparações múltiplas. Não demonstram generalização.
Não foram usados dados reservados de seleção ou avaliação final.

## SimpleBlob: precisão maior, sem ganho agregado de F1

R4c05 elimina 139 FP, mas perde 62 TP frente ao melhor controle: 61 normais
e um pequeno. Melhora em cinco vídeos, com mediana das diferenças de F1
−0,010389. Favorece especialmente vídeos 11, 22 e 23, mas perde nos 35, 36,
47 e 60. Escolher por precisão isolada ocultaria essas perdas.

Área80 favorece margem 2 no agregado; área 64 favorece margem 3. A interação
do efeito margem 3−2 entre área 80 e 64 é −0,018366, intervalo exploratório
−0,031767 a −0,004477, com três diferenças positivas e nove negativas.
Área e caixa continuam precisando ser estudadas conjuntamente.

## DoG: os novos extremos foram excessivos

| Resposta, margem 6 | Candidatos | TP | FP | F1 | Recall |
|---|---:|---:|---:|---:|---:|
| 0,12 | 5.217 | 2.402 | 2.815 | 0,544980 | 0,667593 |
| 0,16 | 2.946 | 1.683 | 1.263 | 0,514364 | 0,467760 |
| 0,20 | 1.650 | 1.087 | 563 | 0,414253 | 0,302112 |
| 0,24 | 648 | 432 | 216 | 0,203486 | 0,120067 |

Subir 0,12→0,16 remove 1.552 FP, mas perde 719 TP. A sensibilidade muda
muito entre vídeos: no35, TP cai de 189 para 2 e F1 de 0,48649 para 0,00840.
Subir para 0,24 piora frente a 0,12 nos 12 vídeos. A maior precisão decorre
também de prever muito menos objetos; não significa detector melhor.

Margem8 piora o F1 agregado nos quatro limiares. Em resposta 0,12, reduz
o total em 140 TP e aumenta FP e FN em 140, sem mudar candidatos.
Não é justificável continuar ampliando todas as caixas
apenas porque parte dos FN possuía caixas pequenas.

## LoG: pequena mudança geométrica, mesmo compromisso entre classes

Margem5 não superou6 em nenhuma das duas respostas no agregado, embora
tenha ajudado alguns vídeos. O ganho de 6 sobre5 em resposta 0,12 é pequeno
e variável; nenhuma dessas configurações novas superou a referência.

Resposta0,12 supera0,08 em F1 nos 12 vídeos, porém os pequenos localizados
caem de 17 para 5 e os aglomerados de 25 para 14. O F1 de indivíduos agrega
normais e pequenos e recebe maior influência da classe mais frequente.
A cobertura por classe precisa continuar visível, sem mudar o critério
depois de observar os resultados.

As contagens de candidatos diminuíram com os limiares, mas os conjuntos
não são subconjuntos perfeitos. Nas três transições consecutivas do DoG
apareceram 86, 13 e dois candidatos diferentes; no LoG, de 0,08 para 0,12,
apareceram 723, apesar da redução do total de 13.490 para 7.959. Compararam-se
centro, sigma, diâmetro, área e classe, ignorando índices renumerados.
Portanto, filtrar o CSV anterior não reproduz necessariamente outro limiar.

## Caixas e classificação

Os candidatos brutos são idênticos nos 178 quadros dos nove pares de margem.
Os três melhores métodos também reproduzem os candidatos e classes dos
respectivos controles do round3. Isso permite atribuir os contrastes de
margem à geometria, mantendo separadas as mudanças de resposta e área.

O melhor DoG localiza 2.402 normais, mas rotula 1.275 deles como pequenos;
não localiza nenhum pequeno anotado. No melhor SBD, os três pequenos
localizados recebem rótulo normal. A classificação não foi corrigida
pela melhora de precisão de algumas variantes.

Mudar somente o corte entre0 e 2 não altera F1 de indivíduos, pois ambas
as classes pertencem ao mesmo grupo. Já confundir indivíduo com aglomerado
afeta os acertos de localização, porque o pareamento é separado por grupo.
Esse problema deve permanecer distinguível de candidato ausente ou caixa ruim.

Há 33 FN normais no SBD e 167 no LoG com alguma caixa prevista como aglomerado
que alcança IoU≥0,50. Isso evidencia erro na fronteira entre grupos, mas
não representa ganho garantido: candidatos podem competir por anotações.
Não houve alteração de classes nem novo pareamento para contabilizar acertos.

A geometria também permanece dispersa. Entre713 FN normais da nova r4c05
que possuem centro do grupo correto, a razão mediana de área caixa/anotação
é1,102, mas228 caixas ficam abaixo da metade e 228 acima do dobro. Uma
mediana próxima de 1 não significa que todas as caixas estejam ajustadas.

## Direção recomendada, ainda sem plano do round5

- Refinar conjuntamente área e caixa do SBD na região já delimitada,
  preservando os controles com melhor F1 e maior cobertura.
- No DoG, investigar o interior da região de resposta próxima da referência,
  com margens moderadas. Evitar prolongar aumentos que derrubaram recall.
- No LoG, preservar o diagnóstico de pequenos e da classificação entre
  indivíduo e aglomerado; ajustes de caixa sozinhos não resolvem todos os erros.

São109 configurações distintas acumuladas, com 14 vagas no último round
e até 13 novas dentro do teto122. A lista numérica do round5 ainda não foi
escolhida nem congelada nesta análise. Nenhum detector, treino ou novo
experimento foi executado; somente documentos e estatísticas foram registrados.

Após o round5, produzir o documento explicativo completo de blobs antes
da seleção em outras imagens e dos vídeos. O k-NN permanece na etapa híbrida.
