# Watershed — plano do round3

21/09/2026. Refinamento aprovado após a [análise do round2](analise_round2_watershed.md).
Plano executável: [round3.json](../scripts/watershed/rodadas/round3.json).
A execução real fica com o pesquisador.

## Objetivo e orçamento

Comparar **24 configurações nos mesmos 178 quadros**: 4.272 avaliações,
com **seis controles e 18 configurações novas**. São 12 pares: separar
regiões ou preservar componentes classificados como aglomerados por área.
Ao concluir a rodada, haverá 94 configurações distintas entre round1 e round3.

O maior F1 do round2 foi 0,466361, mas as melhores configurações ficaram
próximas. A redução de FP veio acompanhada de perda de TP; apenas 7/134
pequenos foram localizados pela líder. O desenho concentra a busca sem
supor que a primeira posição seja uma solução definitiva.

## Parâmetros e motivos

| Par | IDs — separar / preservar | Área mínima | Semente | Ajuste Otsu | Papel |
|---|---|---:|---:|---:|---|
| p01 | r3c01 / r3c02 | 120 | 0,35 | 0 | Controles r2c09 / r2c10 |
| p02 | r3c03 / r3c04 | 120 | 0,50 | 0 | Controles r2c31 / r2c32 |
| p03 | r3c05 / r3c06 | 120 | 0,75 | 0 | Controles r2c11 / r2c12 |
| p04 | r3c07 / r3c08 | 108 | 0,35 | 0 | Área intermediária abaixo de 120 |
| p05 | r3c09 / r3c10 | 132 | 0,35 | 0 | Área intermediária acima de 120 |
| p06 | r3c11 / r3c12 | 108 | 0,75 | 0 | Área intermediária com outra semente |
| p07 | r3c13 / r3c14 | 132 | 0,75 | 0 | Área intermediária com outra semente |
| p08 | r3c15 / r3c16 | 120 | 0,60 | 0 | Semente entre 0,50 e 0,75 |
| p09 | r3c17 / r3c18 | 120 | 0,35 | -5 | Otsu menos restritivo, ajuste pequeno |
| p10 | r3c19 / r3c20 | 120 | 0,35 | +5 | Otsu mais restritivo, ajuste pequeno |
| p11 | r3c21 / r3c22 | 120 | 0,75 | -5 | Mesmo ajuste com outra semente |
| p12 | r3c23 / r3c24 | 120 | 0,75 | +5 | Mesmo ajuste com outra semente |

**Área 108 e 132:** ficam entre os níveis já testados 96/120 e 120/144.
Mínimo 120 superou 96 no agregado, enquanto 144 perdeu para 120 nas quatro
combinações de semente e política. Os passos de 12 pixels investigam essa
vizinhança; não foram estimados como ótimos.

**Semente 0,60:** investiga o intervalo competitivo entre 0,50 e 0,75.
Os seis controles permitem comparar também 0,35, mantendo área, máscara
e política. Não se trata de uma semente aleatória: é a fração da distância
máxima local usada para formar os marcadores do watershed.

**Otsu -5 e +5:** usam metade dos deslocamentos mais próximos testados no
round2. Os ajustes anteriores perderam no agregado, mas -10 melhorou sete
vídeos e piorou cinco. Os novos níveis testam alterações menores e o possível
efeito conjunto com a semente, conservando referências com ajuste zero.

**Seis controles:** incluem as sementes 0,35/0,50/0,75 nas duas políticas.
Isso preserva a líder r2c10, a segunda r2c32, os resultados competitivos de
semente 0,75 e os seus pares para comparação. As demais configurações
históricas continuam disponíveis para a seleção posterior.

## O que permanece fixo

- Otsu na imagem original, polaridade clara, sem abertura; fechamento
  retangular 5×5 com uma iteração e conectividade 8.
- Área máxima 5.000; classe pequeno até 120; aglomerado a partir de 900.
- Caixas delimitam as regiões segmentadas; não há expansão, novo filtro
  de forma, pré-processamento ou mudança no algoritmo nesta rodada.
- Mesmos 178 quadros de desenvolvimento; exclusões 23/900 e 23/1100.
  Imagens, anotações, vídeos reservados e métricas preservados.
- F1 de localização de indivíduos 0+2 como critério principal; grupo 1
  separado; IoU ≥ 0,50 e pareamento exclusivo; classificação 0/2 registrada
  separadamente. Somam-se contagens antes do F1; empates exatos permanecem.
- Grade dirigida determinística, sem sorteio. Seed 42 é registrada para
  continuidade do protocolo; o plano congelado define exatamente a rodada.

Com mínimo 132 não se emite classe 2; com mínimo 120, apenas regiões de
exatamente 120 pixels podem recebê-la; com mínimo 108, a faixa é 108–120.
Por isso, cobertura de pequenos e erros de classificação devem ser lidos
separadamente da acurácia condicional, que pode parecer alta pelo predomínio
de normais. Os rótulos da base permanecem os mesmos.

## Comparações previstas

Cada configuração nova possui `contraste_com` no plano, apontando para um
controle com **somente um parâmetro diferente**, na mesma política:

- p04/p05 contra p01; p06/p07 contra p03: efeito da área mínima.
- p08 contra p02: efeito da semente 0,50 → 0,60. Os quatro níveis de
  semente também podem ser comparados nas bases de área 120 e ajuste zero.
- p09/p10 contra p01; p11/p12 contra p03: efeito do ajuste do limiar.
- Dentro de cada par: somente a política de aglomerados muda.

O PDF mantém visão geral, variação por vídeo, cobertura das classes, ranking
completo e políticas em pares. A quinta página mostra os 18 contrastes novos
com diferenças de F1, TP, FP, FN e cobertura de pequenos. O F1 aparece com
seis casas decimais no round3, para evitar que configurações próximas pareçam
empatadas apenas pelo arredondamento. A ordenação continua usando frações exatas.

Depois da execução, conferir controles, contagens, desempenho por vídeo,
perdas por geometria e estabilidade das posições. O ranking de desenvolvimento
não escolhe finalistas. Nenhum round4 foi preparado nesta etapa.

## Execução e reprodução

Na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round3
```

Conferir entradas sem executar o detector:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round3 --conferir
```

Recuperar somente o PDF de um batch com métricas concluídas:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round3 --somente-relatorio "CAMINHO_COMPLETO_DO_BATCH"
```

Saída: `resultados/frame-to-frame/watershed/round3/batch__<UTC>/`, com
as mesmas pastas por configuração e quadro, comparações, máscaras, mapas,
detecções, avaliações, CSVs, `segmentacao.json`, controles e PDF.
Cada execução cria outra pasta; resultados anteriores não são sobrescritos.
Uma interrupção preserva os arquivos parciais; a próxima execução começa
outra pasta, sem retomada automática do batch interrompido.

O gerador `scripts/watershed/planejamento_round3.py` reproduz exatamente
o JSON salvo ou recusa sobrescrever um plano diferente. Ele não é necessário
para executar o plano já preparado. Os hashes vinculam a configuração aos
resultados conferidos do round2, à análise e aos mesmos arquivos de entrada.

## Compatibilidade e arquivos envolvidos

Durante a execução, seis controles × 178 quadros = **1.068 casos** serão
comparados com o round2, em quatro arquivos cada: `predicoes.txt`,
`deteccoes.csv`, `avaliacao.json` e `diagnostico.json` — 4.272 comparações
de arquivos. Os tempos e títulos das imagens não fazem parte desse teste
de identidade. Qualquer divergência interrompe a execução e preserva as saídas.

Os detectores, o escritor de saídas e as métricas permanecem iguais aos do
round2. Foram estendidos quatro módulos de infraestrutura: comando principal,
conferência compartilhada, relatório comum e conferência dos metadados.
O código histórico permanece em `origens/round2_codigo.zip`; o novo
`codigo.zip` arquivará as 32 fontes usadas nesta etapa.

| Função | Arquivos criados ou atualizados |
|---|---|
| Plano e geração | `scripts/watershed/planejamento_round3.py`, `scripts/watershed/rodadas/round3.json` |
| Execução | `scripts/watershed/execucao_round3.py`, `execucao_round2.py`, `executar_rodada.py` |
| Relatório | `analise/relatorio_round3_watershed.py`, `relatorio_round2_watershed.py`, `relatorio_rodada_watershed.py` |
| Testes | `scripts/testes/test_round3_watershed.py`, auxiliar sintético de `test_relatorio_round2_watershed.py` |
| Documentação | Este plano, estado da pesquisa e guias de execução |

A conferência das entradas passou: **4.634 hashes de origem**, 178 imagens
e 1.068 casos de referência disponíveis. A conferência não executa detectores
nem demonstra que as configurações novas terão melhor desempenho.

Passaram **56 testes sintéticos**: 45 anteriores e 11 novos, incluindo
execução, controles, interrupções, integridade e recuperação do relatório.
As cinco páginas da prévia fictícia do PDF foram conferidas visualmente.
As conferências de entrada das três rodadas passaram; a leitura dos resultados
históricos preservou as 8.544 avaliações e 24 controles do round1 e as
5.696 avaliações e 712 controles do round2. Nenhum batch real do round3
foi executado nesta preparação.
