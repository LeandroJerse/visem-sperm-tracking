# Blobs — análise do round5

20/09/2026. Análise das saídas salvas, sem executar detectores novamente.
Batch: `resultados/frame-to-frame/blobs/round5/batch__20260921T001209933359Z`
(identificador em UTC).

**O round5 aumentou ligeiramente o maior F1 observado, de 0,567571 para
0,568779.** A diferença de +0,001208 equivale a aproximadamente
**+0,121 ponto percentual**. O novo SBD reduz falsos positivos, mas também
perde acertos. O LoG melhora após alterar exclusivamente o limite entre
indivíduo e aglomerado; a maior parte desse ganho vem de um vídeo. Os dois
ganhos têm intervalos exploratórios que incluem zero.

A execução está íntegra. Os resultados sustentam encerrar as cinco rodadas
de desenvolvimento e documentar suas conclusões, sem afirmar que o ótimo
foi encontrado ou escolher finalistas nesta análise.

O [plano executado](plano_round5_blobs.md) registra as hipóteses anteriores
à rodada. As [estatísticas completas](estatisticas_round5_blobs.json)
contêm 14 configurações, nove referências históricas, 41 contrastes,
contagens por vídeo, receita de reprodução e hashes de nove fontes.

## Integridade e reprodução

- **14 configurações × 178 quadros = 2.492 avaliações completas.**
- **363 hashes de entradas/origens e 17.532 de saídas** conferidos, sem
  arquivos ausentes ou divergências.
- Cadeia v5 validada, com seis origens arquivadas: desenvolvimento,
  inspeção e planos dos rounds 1 a 4. Os planos históricos foram preservados.
- ZIP íntegro com **25 arquivos de código**, todos iguais às fontes atuais
  no momento da auditoria.
- Métricas dos 2.492 JSONs por quadro conferem com os CSVs. Os 14 agregados
  foram recalculados a partir das avaliações salvas; 168 resumos por vídeo,
  resumos locais das configurações e ranking também conferem.
- PDF confirmado com **quatro páginas**; apontador, hash e cópias das fontes
  correspondem ao batch concluído.

| Controle | Referência | F1 indivíduos | Quadros reproduzidos |
|---|---|---:|---:|
| r5c03 | r4c03 | 0,552571 | 178 |
| r5c04 | r4c04 | 0,567571 | 178 |
| r5c10 | r4c07 | 0,544980 | 178 |
| r5c13 | r4c18 | 0,428430 | 178 |

Os quatro controles reproduziram **712 avaliações**, desconsiderando apenas
IDs e tempos. Foram conferidos **3.560 arquivos CSV/YOLO idênticos byte a byte**,
incluindo 20.904 registros de candidatos brutos e caixas. Entradas,
dependências registradas e código dos detectores, adaptação de caixas,
classificação e avaliação permaneceram iguais ao round4. Repetições verificam
reprodução computacional; não acrescentam amostras biológicas independentes.

O ambiente registrado foi Python 3.13.3, NumPy 2.3.3, OpenCV 4.13.0
(`opencv-python` 4.13.0.92), SciPy 1.16.2, scikit-image 0.26.0 e ReportLab 4.5.1.

## Resultados principais

Cada configuração utiliza **3.464 anotações normais, 134 pequenas e 109
aglomeradas**. São ocorrências em quadros, não indivíduos únicos. F1,
precisão e recall da tabela referem-se ao grupo de indivíduos 0/2.

| Configuração | Método e parâmetros | F1 | Precisão | Recall | TP / FP / FN | Localizadas 0 / 2 / 1 |
|---|---|---:|---:|---:|---|---|
| r5c04 | SBD área 64/margem 3; controle | 0,567571 | 0,557162 | 0,578377 | 2.081 / 1.654 / 1.517 | 2.078 / 3 / 0 |
| r5c06 | SBD área 72/margem 3; melhor observada | **0,568779** | 0,566428 | 0,571151 | 2.055 / 1.573 / 1.543 | 2.052 / 3 / 0 |
| r5c08 | DoG resposta 0,10/margem 6 | 0,501980 | 0,384718 | 0,722068 | 2.598 / 4.155 / 1.000 | 2.598 / 0 / 0 |
| r5c10 | DoG resposta 0,12/margem 6; controle | 0,544980 | 0,460418 | 0,667593 | 2.402 / 2.815 / 1.196 | 2.402 / 0 / 0 |
| r5c12 | DoG resposta 0,14/margem 6; melhor DoG nova | 0,536669 | 0,509882 | 0,566426 | 2.038 / 1.959 / 1.560 | 2.038 / 0 / 0 |
| r5c13 | LoG resposta 0,12/margem 6; corte aglomerado 24 | 0,428430 | 0,317324 | 0,659255 | 2.372 / 5.103 / 1.226 | 2.367 / 5 / 14 |
| r5c14 | Mesmo LoG; corte aglomerado 28 | 0,442669 | 0,323537 | 0,700667 | 2.521 / 5.271 / 1.077 | 2.516 / 5 / 14 |

No SBD, a distância mínima permanece em 6. Nos LoG, os cortes 24 e 28
indicam diâmetros equivalentes em pixels: a área mínima de aglomerado passa
de π×12² para π×14². O cálculo usa a área circular estimada do candidato,
não a área da caixa anotada.

## Análise estatística

Mantidos indivíduos 0/2 juntos, aglomerados separados, IoU≥0,50, pareamento
exclusivo e **F1 calculado depois de somar TP, FP e FN**. Trocas de classe
0↔2 continuam registradas separadamente dos acertos de localização.

Foi utilizado bootstrap exploratório pareado por vídeo: 12 blocos,
10.000 reamostragens e `numpy.random.default_rng(42)`. Cada bloco reúne
todos os frames anotados disponíveis de um vídeo; não são vídeos completos
processados nesta etapa nem 178 observações independentes. Uma única matriz
de índices é aplicada a todas as configurações e termos dos contrastes.
Os intervalos usam percentis 2,5 e 97,5 com interpolação linear. Vitórias,
empates e derrotas usam frações exatas de F1, sem arredondamento.

**Na tabela abaixo, ΔF1 e os intervalos são frações de F1, não pontos
percentuais.** Por exemplo, +0,010 corresponde a +1 ponto percentual.

| Contraste: variante − referência | ΔF1 agregado | Melhora/empate/piora por vídeo | Intervalo 95% exploratório |
|---|---:|---|---|
| Melhor nova r5c06 − controle r5c04 | +0,001208 | 7/0/5 | −0,007846 a +0,011547 |
| SBD área 72 − 64, margem 2 | +0,010673 | 8/0/4 | +0,001915 a +0,019084 |
| SBD margem 3 − 2, área 72 | +0,005536 | 7/0/5 | −0,050926 a +0,057174 |
| Interação SBD: efeito da margem 3−2 na área 72 menos o efeito na área 56 | −0,019975 | 4/0/8 | −0,033565 a −0,005285 |
| DoG margem 6 − 5, resposta 0,12 | +0,039705 | 9/0/3 | +0,007415 a +0,083739 |
| DoG resposta 0,12 − 0,10, margem 6 | +0,043000 | 11/0/1 | +0,005730 a +0,070449 |
| DoG resposta 0,14 − 0,12, margem 6 | −0,008311 | 7/0/5 | −0,064841 a +0,032183 |
| LoG corte aglomerado 28 − 24 | +0,014239 | 6/1/5 | −0,006199 a +0,051938 |
| Melhor SBD r5c06 − melhor DoG r5c10 | +0,023799 | 6/0/6 | −0,078101 a +0,118348 |
| Melhor SBD r5c06 − melhor LoG r5c14 | +0,126110 | 11/0/1 | +0,035254 a +0,206930 |

Os 41 contrastes tiveram 10.000 reamostragens definidas, sem exclusões por
ausência de casos. Contrastes entre controles repetidos e referências
históricas coincidem numericamente e não constituem evidências independentes.

Os intervalos são condicionais aos 12 vídeos já utilizados. Não corrigem
a busca adaptativa, a escolha dos maiores valores observados ou comparações
múltiplas. Também não demonstram independência entre participantes nem
generalização. Não foram usados valores-p ou intervalos para selecionar
configurações. Os dados reservados de seleção e avaliação final permaneceram
fora desta análise.

## SimpleBlob: ganho pequeno, com perda de cobertura

R5c06 retira **81 FP**, mas perde **26 TP**, todos normais, frente à r5c04.
Mantém os três pequenos localizados. A precisão sobe de 0,557162 para
0,566428, enquanto o recall cai de 0,578377 para 0,571151. O aumento de F1
é **+0,001208154456**, com mediana das diferenças por vídeo +0,003129.
Melhora em sete vídeos e piora em cinco.

Esse ganho é pequeno diante do intervalo exploratório −0,007846 a
+0,011547. A ordenação descritiva coloca r5c06 à frente, mas não demonstra
superioridade estável em novos vídeos. R5c04 preserva mais acertos e deve
continuar visível na discussão dos compromissos entre precisão e recall.

A interação entre área e margem persiste. Aumentar a margem de 2 para 3
acrescenta 95 TP na área 56, 55 na área 64 e 20 na área 72, sem alterar os
candidatos de cada par. O ganho de margem diminui conforme aumenta a área
mínima nesta grade. Comparar somente uma dessas variáveis ocultaria esse
comportamento.

## DoG: a referência continua com o melhor F1 do método

Reduzir a resposta de 0,12 para 0,10, com margem 6, acrescenta 196 TP,
mas também **1.340 FP**. O recall sobe para 0,722068, porém o F1 cai para
0,501980. A quantidade de acertos isoladamente não indica a melhor
configuração.

Aumentar a resposta de 0,12 para 0,14 retira **856 FP**, mas perde **364 TP**.
O F1 cai de 0,544980 para 0,536669. Essa variante melhora em sete vídeos e
piora em cinco; o F1 agregado pondera suas contagens, não a quantidade de
vídeos em que houve melhora. A maior precisão da resposta 0,14 não supera
a perda de cobertura no critério acordado.

Margem 6 supera margem 5 no agregado nos três limiares. Na resposta 0,12,
acrescenta 175 TP e retira 175 FP, preservando os candidatos brutos. Assim,
a rodada confirmou a utilidade dessa margem na região estudada, sem
justificar uma nova expansão indiscriminada das caixas.

## LoG: melhora da fronteira de classe, concentrada em um vídeo

R5c14 altera exclusivamente `classificacao.area_minima_aglomerado` de
π×12² para π×14². Permanecem iguais resposta, pré-processamento, centro,
sigma, diâmetro, área estimada e geometria das caixas. A comparação dos
arquivos salvos confirmou **7.959 candidatos idênticos** nos 178 quadros,
com **317 mudanças de classe 1 para 0**.

Os 317 candidatos eram falsos positivos de aglomerados na referência:

- **149 passam a formar pares com indivíduos anotados**, todos normais.
- **168 continuam sem par**, agora contabilizados como falsos positivos
  de indivíduos.

Nenhum acerto anterior foi perdido: os **2.386 pares anteriores** continuam
os mesmos, correspondendo a 2.372 indivíduos e 14 aglomerados. Portanto,
o ganho de localização ocorre porque previsões existentes passam ao grupo
correto de correspondência; não foram criados candidatos nem corrigidas
as caixas ou anotações.

| Medida | r5c13: corte 24 | r5c14: corte 28 |
|---|---:|---:|
| TP indivíduos | 2.372 | 2.521 |
| FP indivíduos | 5.103 | 5.271 |
| FN indivíduos | 1.226 | 1.077 |
| TP aglomerados | 14 | 14 |
| FP aglomerados | 470 | 153 |
| FN aglomerados | 95 | 95 |
| F1 aglomerados | 0,047218 | 0,101449 |

O F1 de indivíduos sobe +0,014239, mas **130 dos 149 TP adicionais (87,25%)**
estão no vídeo 35. O contraste melhora em seis vídeos, empata em um e piora
em cinco; a mediana por vídeo é apenas +0,000245. O intervalo exploratório
−0,006199 a +0,051938 inclui zero.

Como diagnóstico de sensibilidade, ao retirar apenas o vídeo 35 das somas,
a diferença torna-se **−0,002998**. Essa conta não altera a métrica oficial
nem autoriza excluir o vídeo: mostra quanto a conclusão agregada depende
de sua presença. O corte 28 merece registro como melhoria observada neste
painel, sem ser tratado como regra geral de classificação.

## Limitações ainda presentes

Nas melhores configurações observadas de cada método, a cobertura dos
134 pequenos é **3 no SBD, zero no DoG e 5 no LoG**. Os três pequenos
localizados pelo SBD recebem rótulo normal. O DoG r5c10 localiza 2.402
normais, mas rotula **1.275 como pequenos**; LoG r5c14 faz essa troca em
793 normais. Localização e classificação continuam sendo problemas
distintos, mesmo quando o F1 de indivíduos melhora.

Também permanece um grande volume de previsões sem correspondência. Entre
os FP de indivíduos, o centro previsto fica fora de todas as caixas
anotadas em **853/1.573 casos no SBD r5c06**, **1.905/2.815 no DoG r5c10**
e **3.654/5.271 no LoG r5c14**. Trata-se de um diagnóstico geométrico
descritivo, não de uma classificação exaustiva das causas de erro nem de
uma afirmação de que todos esses candidatos são ruído biológico.

Nos **seis pares de margem** da rodada, os candidatos brutos permanecem
iguais nos 178 quadros. Isso sustenta atribuir as diferenças desses pares
à adaptação das caixas neste painel. Não permite concluir que um único
tamanho de caixa resolveria candidatos ausentes, previsões sem objeto
anotado e trocas entre indivíduo e aglomerado.

## Encerramento recomendado das cinco rodadas

O round5 acrescenta **dez configurações novas e quatro controles**. As cinco
rodadas somam **136 posições de configuração e 119 configurações distintas**,
dentro do teto de 122. Não é necessário esgotar o teto para encerrar a busca.

Recomenda-se encerrar este desenvolvimento: o melhor SBD teve ganho pequeno,
o DoG preservou a referência e o LoG mostrou uma correção de fronteira
dependente da composição dos vídeos. As limitações das classes pequenas,
dos aglomerados e das falsas detecções estão identificadas e devem acompanhar
as comparações futuras.

A consolidação do processo em `desenvolvimento_blobs.html` deve explicar as
hipóteses, os desenhos e as decisões das cinco rodadas. Nenhuma das cinco
finalistas foi escolhida aqui. A seleção nas outras imagens e a avaliação
em vídeos continuam como etapas posteriores, a serem preparadas no escopo
acordado. Não foi preparado round6, novo detector ou treinamento; o k-NN
permanece previsto para a etapa híbrida.

## Fontes e rastreabilidade

As métricas e os intervalos desta análise vêm de
[estatisticas_round5_blobs.json](estatisticas_round5_blobs.json), cujo SHA256
no momento da redação é
`bf14f51a6882b301b3aedea48b56273303cc35d413e1105fffa226858beb0b84`.
Suas nove fontes foram novamente conferidas por hash.

O [manifesto do batch](../resultados/frame-to-frame/blobs/round5/batch__20260921T001209933359Z/execucao.json)
registra os caminhos e hashes individuais de entradas, saídas e código.
Identificadores da auditoria:

| Arquivo | SHA256 |
|---|---|
| `execucao.json` | `5799f87cc6e48692104fe97eadfe2baf20a76dba4fdbbc7c41ae8d329efcfaba` |
| `plano.json` | `bfd27624ff6f84bcd5e80c96195449b6762ecb74fc3c23b5c0478495b387032f` |
| `codigo.zip` | `12569be01c9a8a4282e74c542c18372d8db0034816546d5079a65e53af8ecf89` |
| PDF da execução | `b657a23d680a4c036106968689511e7399c869bfae23ba2ac9cb878277ce4d20` |

O diagnóstico geométrico utiliza 2.136 arquivos: `deteccoes.csv`,
`anotacoes.csv` e `pares.csv` dos 178 quadros de r5c06, r5c10, r5c13 e r5c14.
A impressão digital desse conjunto é
`10beb41f0e423f22de925a27d3d4541bee3e59d2f7e420581d678d048db23ec7`.
Para reproduzi-la, ordenar os caminhos relativos ao projeto, escrever uma
linha por arquivo como `caminho<TAB>sha256<LF>`, incluindo o LF final, codificar
em UTF-8 e calcular SHA256. Os hashes individuais constam no manifesto.

A análise estatística utiliza o ambiente de análise registrado no JSON:
Python 3.12.14 e NumPy 2.3.5. Esse ambiente lê os resultados salvos e é
distinto do ambiente de execução dos detectores registrado acima.
