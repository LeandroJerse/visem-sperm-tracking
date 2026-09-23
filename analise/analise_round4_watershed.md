# Watershed — análise do round4

21/09/2026. Análise dos resultados salvos, sem nova execução do detector.
Batch: `resultados/frame-to-frame/watershed/round4/batch__20260921T184319705365Z`.
As [estatísticas completas](estatisticas_round4_watershed.json) preservam
contagens, parâmetros, contrastes, hashes e diagnóstico das perdas.

**Conclusão:** execução íntegra e ganho pequeno no desenvolvimento.
O maior F1 passou de **0,478007 para 0,481308**, com 12 acertos adicionais
e 15 falsas detecções a menos. Semente 0,50, ajuste Otsu −3 e fechamento
3×3 produziram alternativas competitivas, mas ainda não foram combinados.
As primeiras posições são próximas e sensíveis à composição dos vídeos.
Vale concluir o desenvolvimento com um round5 limitado a essas combinações.

## Conferência da execução

- **18 configurações × 178 quadros = 3.204 avaliações** concluídas.
- **42.769 hashes de saídas e 4.635 de origens** conferidos, sem divergências.
- **1.068 controles**, com 4.272 arquivos de previsões, detecções, avaliações
  e diagnósticos idênticos ao round3.
- 35 fontes arquivadas, íntegras e iguais às fontes atuais.
- Tabelas completas: 18 configurações, 216 linhas por vídeo e 3.204 por quadro.
  Agregações, ranking, parâmetros e metadados de segmentação reconciliados.
- As 3.204 avaliações JSON e tabelas de pares coincidem com as métricas
  registradas. Cada quadro possui os doze arquivos previstos.
- Os pareamentos dos 178 quadros da líder r4c16 foram recalculados das caixas
  salvas e coincidiram integralmente com as avaliações.
- PDF original de cinco páginas, hash e 11.797 fontes conferidos. Todas as
  páginas foram inspecionadas visualmente, assim como r4c16 e r4c04 em 30/700
  e r4c16 em 60/1300. Esses exemplos ilustram ganho e perda por quadro;
  foram escolhidos após consultar as diferenças, não como amostra aleatória.

A execução registrada durou **15 minutos e 4 segundos**, antes do PDF.
Nenhuma imagem original, anotação, configuração executada ou resultado foi alterado.

## Resultado principal

| Medida | Líder round3, repetida em r4c04 | Líder round4, r4c16 |
|---|---:|---:|
| F1 de indivíduos | 0,478007 | **0,481308** |
| Precisão | 0,448284 | 0,451534 |
| Recall | 0,511951 | 0,515286 |
| Acertos — TP | 1.842 | 1.854 |
| Falsas detecções — FP | 2.267 | 2.252 |
| Perdas — FN | 1.756 | 1.744 |
| Normais localizados | 1.835/3.464 | 1.844/3.464 |
| Pequenos localizados | 7/134 | 10/134 |
| Aglomerados localizados | 46/109 | 46/109 |
| F1 de aglomerados | 0,224939 | 0,224939 |

A diferença de F1 é **+0,003301**, ou **+0,33 ponto percentual** na escala
de 0 a 100%. F1 não é porcentagem de objetos encontrados; essa medida é o recall.
O ganho de localização se divide em nove normais e três pequenos adicionais.

A líder mantém Otsu −5, polaridade clara, abertura desligada, fechamento
retangular 5×5, mínimo 120 e preservação de aglomerados por área. Somente
a fração de semente muda de 0,35 para **0,50** frente à referência r4c04.
Máximo 5.000, pequeno até 120 e aglomerado a partir de 900 permanecem iguais.

| Posição | Configuração | Otsu | Semente | Mínimo | Fechamento | Política | F1 indivíduos |
|---:|---|---:|---:|---:|---:|---|---:|
| 1 | r4c16 | −5 | 0,50 | 120 | 5×5 | preservar | 0,481308 |
| 2 | r4c15 | −5 | 0,50 | 120 | 5×5 | separar | 0,480515 |
| 3 | r4c08 | −3 | 0,35 | 120 | 5×5 | preservar | 0,480408 |
| 4 | r4c18 | −5 | 0,35 | 120 | 3×3 | preservar | 0,480083 |
| 5 | r4c14 | −5 | 0,35 | 144 | 5×5 | preservar | 0,478960 |

Estas posições não são as cinco finalistas. Após o desenvolvimento, todas
as configurações distintas deverão passar pela etapa de seleção acordada.

## Interpretação dos contrastes

### Semente 0,50

É o refinamento mais promissor desta rodada: melhora nas duas políticas,
ganhando TP e reduzindo FP. Separando regiões, há **+27 TP e −87 FP**,
com F1 de 0,470146 para 0,480515. Preservando, há **+12 TP e −15 FP**,
com F1 de 0,478007 para 0,481308. Ambos os pares recuperam três pequenos.

A máscara de entrada permanece igual, com média de 5,73% dos pixels.
O efeito vem da mudança dos marcadores e da divisão das regiões, não de
um limiar diferente. Em 30/700, as imagens ilustram a separação de caixas
antes unidas; o quadro ganha dois TP. Isso não ocorre em todos os quadros.

Preservar, comparado a separar com semente 0,50, perde 51 TP e elimina
174 FP. O ganho líquido em F1 é só 0,000794. Não há justificativa para
abandonar uma das políticas antes da seleção em outras imagens.

### Ajuste de Otsu

**−3 supera −5** no agregado nas duas políticas, com semente 0,35:
perde três a quatro TP e elimina 48–76 FP. Na preservação, melhora seis
vídeos e piora seis. A máscara média diminui de 5,73% para 5,38% dos pixels.

**−7 perde para −5** nas duas políticas: perde sete a 18 TP e acrescenta
99–135 FP. Melhora quatro vídeos e piora oito. Ampliar mais a máscara
(média de 6,03%) não ajudou no agregado. Não merece prioridade na rodada final.

### Fechamento 3×3

Com Otsu −5, o fechamento menor **melhora as duas políticas**. Preservando,
ganha 14 TP e acrescenta 11 FP, atingindo F1 0,480083. Separando, ganha
21 TP e acrescenta dez FP, atingindo 0,473566. Cada variante recupera um
pequeno adicional. A máscara média passa de 5,73% para 5,40% dos pixels.

O fechamento 3×3 havia perdido com ajuste zero no round2; agora é competitivo
com −5. As sementes das comparações anteriores também diferem, portanto
não se atribui toda a diferença entre rodadas exclusivamente a Otsu.
O contraste atual, dentro do round4, isola somente o fechamento.

### Área mínima

132 e 144 melhoram ligeiramente o F1 nas duas políticas, mas perdem TP
e um pequeno localizado. Na preservação, mínimo 132 remove 87 FP e 26 TP
(ganho de F1 0,000265); mínimo 144 remove 190 FP e 55 TP (ganho 0,000953).
O mínimo 144 é uma hipótese limitada para combinar com semente 0,50,
mantendo explícito o custo em cobertura. A líder atual continua com mínimo 120.

## Variação por vídeo e sensibilidade

Contra r4c04, a líder melhora em **seis vídeos**, piora em **cinco** e empata
em **um**. A mediana das diferenças por vídeo é +0,000917. Ela é apenas
um diagnóstico descritivo; o ranking continua usando F1 após somar contagens.

| Vídeo | F1 anterior | F1 novo | Diferença |
|---|---:|---:|---:|
| 11 | 0,354890 | 0,361484 | +0,006594 |
| 12 | 0,494012 | 0,497765 | +0,003753 |
| 15 | 0,506770 | 0,508604 | +0,001834 |
| 19 | 0,235145 | 0,228070 | −0,007075 |
| 21 | 0,624813 | 0,642314 | +0,017500 |
| 22 | 0,582339 | 0,579572 | −0,002766 |
| 23 | 0,324786 | 0,324786 | 0,000000 |
| 30 | 0,785340 | 0,793734 | +0,008393 |
| 35 | 0,526621 | 0,522749 | −0,003872 |
| 36 | 0,633446 | 0,646362 | +0,012916 |
| 47 | 0,311787 | 0,307087 | −0,004700 |
| 60 | 0,202020 | 0,195980 | −0,006040 |

Ao retirar um vídeo de cada vez, a primeira posição entre as 18 configurações
fica com **r4c16 em seis retiradas, r4c08 em quatro, r4c15 em uma e r4c18
em uma**. A diferença entre primeiro e segundo é apenas **0,000794**.
Essas alternativas devem continuar disponíveis. A análise não é validação
cruzada nem teste de significância, e os quadros de cada vídeo são correlacionados.

## Limitações que permanecem

Dos **1.744 indivíduos perdidos** pela líder:

| Diagnóstico dos candidatos salvos | Quantidade |
|---|---:|
| Sobreposição, mas nenhum candidato alcança IoU 0,50 | 1.625 |
| Nenhum candidato sobreposto | 54 |
| Candidato com IoU suficiente rejeitado por área | 44 |
| Candidato aceito no grupo de aglomerados | 12 |
| Candidato individual válido sem par exclusivo disponível | 9 |

As categorias são exclusivas e sua prioridade está nas estatísticas.
São 1.108 perdas com melhor IoU entre 0,25 e 0,50. Entre os melhores
candidatos dos FN com sobreposição, 791 caixas têm ao menos o dobro da área
anotada e 457 têm menos da metade. A geometria continua sendo a limitação
principal; expandir todas as caixas não tem sustentação.

Dos 2.252 FP individuais, 1.323 não sobrepõem indivíduos anotados, 918 têm
sobreposição insuficiente e 11 correspondem geometricamente a aglomerados.
FP é definido pelas anotações disponíveis, não por uma conclusão biológica
sobre cada objeto da imagem.

**Pequenos: 10/134 localizados (7,46%), todos previstos como normal.**
A matriz dos pares individuais é `[[1843, 1], [10, 0]]`, na ordem
normal/pequeno. A acurácia condicional de 99,41% exclui perdas e FP.
Nenhuma das 18 configurações classificou corretamente como pequeno um
pequeno localizado. A cobertura máxima da rodada foi 10/134.

Dos 124 pequenos perdidos pela líder, 71 têm IoU insuficiente, 48 não
têm candidato sobreposto, quatro foram rejeitados por área e um sofre
competição de pareamento. Alterar apenas o limite entre classes 0/2 não
recuperaria essas perdas de localização. Os limites atuais favorecem emitir
normal: com mínimo 120, classe 2 só pode ocorrer em regiões de 120 pixels.

## Proposta para o round5

Recomenda-se **uma última rodada com 14 configurações: seis controles e
oito novas**, em sete pares separar/preservar. O objetivo é verificar
combinações das melhorias observadas, não somar seus ganhos como se fossem
independentes. Não há plano executável do round5 preparado nesta análise.

| Papel | Otsu | Semente | Mínimo | Fechamento | Quantidade |
|---|---:|---:|---:|---:|---:|
| Controle r4c15/r4c16 | −5 | 0,50 | 120 | 5×5 | 2 |
| Controle r4c07/r4c08 | −3 | 0,35 | 120 | 5×5 | 2 |
| Controle r4c17/r4c18 | −5 | 0,35 | 120 | 3×3 | 2 |
| Combinar limiar e semente | −3 | 0,50 | 120 | 5×5 | 2 |
| Combinar fechamento e semente | −5 | 0,50 | 120 | 3×3 | 2 |
| Combinar os três ajustes | −3 | 0,50 | 120 | 3×3 | 2 |
| Área maior com a semente líder | −5 | 0,50 | 144 | 5×5 | 2 |

A referência com semente 0,50 e as três combinações formam um cruzamento
**Otsu −5/−3 × fechamento 5/3**, mantendo semente 0,50 e mínimo 120.
Assim, o efeito do fechamento pode ser examinado em cada limiar, e vice-versa.
A combinação dos três ajustes deve ser contrastada com cada combinação
de dois ajustes, mudando um parâmetro por comparação. Os controles com
semente 0,35 permitem comparar também o efeito da mudança de semente.

O mínimo 144 recebe somente um par, para examinar a redução de FP sem
ampliar demais a busca. Os controles representam hipóteses e referências;
não são uma seleção antecipada das cinco finalistas. Parâmetros de classe,
detector, caixas, métricas e os 178 quadros permanecem iguais.

Se aprovado e executado, esse desenho levará a **114 configurações distintas**
nos cinco rounds, com 2.492 avaliações no último. Depois, encerrar os ajustes
nesses quadros e preparar a comparação das configurações distintas nos
60 quadros de seleção. Os testes em vídeo vêm após a revisão das cinco
finalistas, mantendo a sequência do protocolo.

## Arquivos desta análise

- Criados: `analise/analise_round4_watershed.md` e
  `analise/estatisticas_round4_watershed.json`.
- Atualizados: `analise/estado_pesquisa.md`, `analise/README.md`,
  `analise/plano_watershed.md`, `README.md`, `scripts/README.md`,
  `scripts/watershed/README.md` e `algoritmos/classicos/README.md`.
- Código, planos executados, imagens, anotações e resultados preservados.
