# Diagnóstico dos candidatos e caixas de blobs — round0

20/09/2026 — diagnóstico dos registros existentes, sem nova execução do detector.

## Conclusão

**Usar diretamente o diâmetro do blob como lado da caixa não representa bem
as anotações nesta inspeção.** A conversão das coordenadas está coerente;
o problema observado é a extensão estimada do objeto. Muitas caixas são
pequenas mesmo quando o centro está próximo do centro anotado.

O formato aproximadamente quadrado continua plausível: nas 167 anotações de
indivíduos, os lados têm medianas de 20 × 20 pixels e a razão entre lado maior
e menor tem mediana de 1,083 e P90 de 1,325. Essa observação não valida uma
regra de tamanho nem representa toda a base.

Há também candidatos excedentes, vários centros dentro de uma anotação e
perdas de pequenos. Portanto, aumentar caixas isoladamente não resolve todos
os problemas. Ainda não foi escolhida ou testada uma adaptação.

## Origem e alcance

- Inspeção: [inspecao__20260920T041252237886Z](../resultados/frame-to-frame/blobs/round0/inspecao__20260920T041252237886Z).
- Diagnóstico: [diagnostico__20260920T175946938558Z](../resultados/frame-to-frame/blobs/round0/diagnostico__20260920T175946938558Z).
- Casos: b01 (claros) e b02 (escuros), nos mesmos seis quadros de desenvolvimento:
  11/0, 12/200, 19/0, 21/0, 23/0 e 36/1300.
- Referência de cada configuração: 160 normais, 7 pequenos e 5 aglomerados.

O diagnóstico usa os centros brutos, caixas e classes já salvos. Um centro
dentro de uma anotação é uma **incidência geométrica**, não um acerto, uma
identidade ou uma correspondência exclusiva. Anotações podem se sobrepor.
Os números abaixo não substituem TP, FP, FN e F1 do avaliador acordado.

## 1. A implementação das caixas está coerente

Foram conferidas as **3.104 detecções** das duas configurações:

- limites da caixa calculados por centro ± metade do diâmetro, com
  arredondamento para fora e recorte nos limites da imagem;
- área circular estimada igual a π × (diâmetro / 2)²;
- classe e coordenadas normalizadas no arquivo YOLO coerentes com a caixa salva.

Não foi encontrada divergência nesses cálculos. Isso confirma a aplicação
da regra atual, mas não que o diâmetro estimado corresponda à cabeça inteira.

## 2. O tamanho é um problema mesmo com centro plausível

Para separar tamanho de multiplicidade, esta tabela usa apenas anotações
de indivíduos que contêm **exatamente um centro**, independentemente da
classe prevista. São subconjuntos descritivos, sem novo pareamento.

| Medida | b01 — claros | b02 — escuros |
|---|---:|---:|
| Anotações de indivíduos com exatamente um centro | 101 | 55 |
| Mediana da área da caixa prevista / área anotada | 17,50% | 9,21% |
| Caixas com área inferior à metade da anotada | 98/101 | 54/55 |
| Distância mediana do centro bruto ao centro anotado | 2,32 px | 4,84 px |
| Centro na metade central da anotação, em ambos os eixos | 90/101 | 29/55 |
| Diâmetro bruto mediano | 6,63 px | 5,04 px |

Quando a caixa prevista tem menos da metade da área anotada, sua IoU não
pode alcançar 0,50 apenas mudando a posição: mesmo inteiramente contida na
anotação, a interseção continua pequena. Isso identifica uma limitação de
tamanho sem executar qualquer expansão experimental.

Exemplo: em **b01, vídeo 36, quadro 1300, anotação 4, detecção 45**, o centro
bruto está a aproximadamente **0,007 px** do centro anotado. A caixa prevista
mede **7 × 6 px**, enquanto a anotação mede **17 × 16 px**; a IoU é **0,154**.
A anotação é normal e a previsão é pequeno. A posição está próxima, mas
a delimitação é insuficiente. A diferença de rótulos é descritiva: esse par
não atende à IoU mínima para contabilizar a classificação no avaliador.

## 3. Os candidatos também precisam de revisão

| Relação geométrica | b01 — claros | b02 — escuros |
|---|---:|---:|
| Detecções totais | 619 | 2.485 |
| Centro fora de todas as anotações | 349 (56,4%) | 2.172 (87,4%) |
| Centro em exatamente uma anotação | 258 | 298 |
| Centro em várias anotações | 12 | 15 |
| Anotações sem centro | 6 | 22 |
| Anotações com exatamente um centro | 101 | 55 |
| Anotações com vários centros | 65 | 95 |

As três últimas linhas abrangem as 172 anotações de cada configuração.
As contagens de incidências são 284 em b01 e 329 em b02; não são quantidades
de objetos localizados. Um candidato fora das caixas anotadas não é
automaticamente um resíduo, e vários centros não comprovam duplicação.
Essas hipóteses dependem de inspeção visual.

| Configuração / classe anotada | Sem centro / um / vários | Mediana da melhor IoU, qualquer classe | Anotações com alguma caixa de IoU ≥ 0,50 |
|---|---:|---:|---:|
| b01 / normal | 0 / 100 / 60 | 0,163 | 2/160 |
| b01 / pequeno | 6 / 1 / 0 | 0,000 | 0/7 |
| b01 / aglomerado | 0 / 0 / 5 | 0,080 | 0/5 |
| b02 / normal | 22 / 48 / 90 | 0,092 | 2/160 |
| b02 / pequeno | 0 / 7 / 0 | 0,203 | 0/7 |
| b02 / aglomerado | 0 / 0 / 5 | 0,074 | 0/5 |

A melhor IoU é o máximo sobre as caixas disponíveis, sem exclusividade;
não é recall. b01 oferece centros dentro das 160 anotações normais, mas
isso não significa 160 acertos. Também deixa seis dos sete pequenos sem
centro. Não há evidência suficiente para descartar uma polaridade agora.

Nos aglomerados, vários candidatos pequenos podem descrever partes da região
sem produzir uma caixa que represente o aglomerado anotado. No vídeo 19,
quadro 0, a anotação 21 contém 17 centros em cada configuração; sua caixa
mede 77 × 81 px. A melhor IoU é 0,041 em b01 e 0,104 em b02.

## 4. Exemplos e limites da inspeção visual

As comparações originais mostram anotações à esquerda e previsões à direita:

- [b01, vídeo 23/quadro 0](../resultados/frame-to-frame/blobs/round0/b01__blobs-claro-t10a250-p10-r2__cfg-31ac6c11fa42__20260920T041252237886Z/quadros/23_frame_0/comparacao.png): quatro anotações e 38 candidatos; caixas pequenas sobre partes brilhantes e muitos centros fora das anotações.
- [b01, vídeo 36/quadro 1300](../resultados/frame-to-frame/blobs/round0/b01__blobs-claro-t10a250-p10-r2__cfg-31ac6c11fa42__20260920T041252237886Z/quadros/36_frame_1300/comparacao.png): exemplo de centro plausível com caixa insuficiente e regiões com vários candidatos.
- [b02, vídeo 12/quadro 200](../resultados/frame-to-frame/blobs/round0/b02__blobs-escuro-t10a250-p10-r2__cfg-f87da89072cc__20260920T041252237886Z/quadros/12_frame_200/comparacao.png): 33 anotações e 262 candidatos; excesso de respostas pequenas. A anotação 30, pequeno, contém um centro em b02 e nenhum em b01.

São observações exploratórias de exemplos, não uma revisão individual de
todos os candidatos. A ficha de revisão humana permanece sem pareceres.
O [guia de revisão gerado](../resultados/frame-to-frame/blobs/round0/diagnostico__20260920T175946938558Z/guia_revisao.md)
permite localizar os demais casos. Há poucos pequenos e aglomerados nesta
amostra intencional; os resultados não estimam o desempenho geral do método.

## 5. Verificações e consequência para a próxima etapa

- **36 testes sintéticos do diagnóstico passaram**: contratos geométricos,
  entradas inválidas, preservação da origem e execução sobre registros salvos.
- Diagnóstico concluído em **12/12 casos**, com 117 hashes de origem e
  21 hashes de saída conferidos. Código arquivado e ZIP íntegros.
- Inspeção original preservada: 14 entradas e 99 saídas conferidas, incluindo
  a integridade e o vínculo do PDF com sua origem.
- Detector, parâmetros, avaliador e dados originais não foram alterados.

Conclui-se a etapa A do [plano de diagnóstico](plano_diagnostico_blobs.md).
Na revisão de continuidade de 20/09/2026, foi acordado preparar o round1
amplo, incorporando candidatos, caixas e classificação à busca formal.
Foram aprovadas as alternativas original/escala/margem. Revisões visuais
adicionais atendem dúvidas concretas, sem exigir calibração completa antes
das rodadas. A evidência não fornece uma escala universal nem elimina a
necessidade de observar os candidatos. A
[síntese de continuidade](estado_pesquisa.md) registra o orçamento e as pendências.

As medianas e percentis foram calculados a partir dos JSONs de diagnóstico;
P90 usa interpolação linear. Não houve nova detecção, expansão de caixas,
busca de parâmetros, ranking ou alteração do critério de avaliação.
