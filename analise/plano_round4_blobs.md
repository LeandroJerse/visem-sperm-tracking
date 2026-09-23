# Blobs — plano do round4

**Execução concluída e conferida.** Os resultados estão na
[análise do round4](analise_round4_blobs.md). Este documento preserva o
desenho e as justificativas registrados antes da execução.

20/09/2026. Continuação do refinamento solicitada após a execução do round3.
Fundamentação: [análise do round3](analise_round3_blobs.md) e
[estatísticas reproduzíveis](estatisticas_round3_blobs.json).

**18 configurações × 178 quadros = 3.204 avaliações.** São cinco repetições
e 13 novas, levando de 96 para **109 configurações distintas acumuladas**.
Permanecem os mesmos dados de desenvolvimento, critérios e orçamento.

## Desenho e justificativas

| Método | Grade | Quantidade | Hipótese |
|---|---|---:|---|
| SimpleBlob | Área mínima48/64/80 × margem2/3; distância6 fixa | 6 | Filtrar candidatos e ajustar a caixa conjuntamente |
| DoG | Resposta0,12/0,16/0,20/0,24 × margem6/8 | 8 | Explorar respostas mais restritivas e expansão onde ainda há caixas pequenas |
| LoG | Resposta0,08/0,12 × margem5/6 | 4 | Reduzir levemente caixas excessivas sem abandonar a faixa que recuperou mais pequenos |

Cada linha é uma grade completa: todos os valores de um fator são combinados
com todos os do outro. Comparar diferenças mantendo os demais parâmetros
fixos permite investigar interações; isso não torna os frames independentes.

### SimpleBlob

Referência de construção: r3c09. Área48/margem3 é preservada porque teve
F1 próximo do líder e encontrou mais indivíduos. Área64/margem3 preserva o
maior F1. Área80 estende moderadamente a faixa; não se presume que continue
melhorando. Margem2 testa redução porque muitos FN com centro candidato
possuem caixas grandes. A interação área × margem foi observada no round3.

Distância6 fica fixa: em área64/margem3, reduzir12→6 mudou F1 em apenas
0,000228, com intervalo exploratório incluindo zero. Não gastar outra dimensão
da grade em uma diferença pequena neste estágio.

Demais parâmetros: polaridade clara, limiares80–220 (máximo exclusivo),
passo5, repetibilidade2, área máxima500, inércia mínima0,4, circularidade e
convexidade desligadas, sem pré-processamento. Pequeno ≤π×3²; aglomerado
≥π×12², medidos na área circular estimada, não na área da caixa adaptada.

### DoG

Referência: r3c24. Resposta0,12 e margem6 foram os melhores extremos testados,
com ganhos presentes nos 12 vídeos nos respectivos contrastes do round3.
Respostas0,16/0,20/0,24 prolongam essa investigação com passo0,04. São
hipóteses de busca; respostas maiores podem eliminar muitos objetos verdadeiros.

Margem8 investiga 318 normais perdidos com candidato sigma2, cuja caixa teve
razão mediana de área0,492 e anotação mediana25×25. Outros candidatos já
possuem caixas grandes; manter margem6 permite medir o custo da expansão.

O melhor DoG do round3 não localizou nenhum pequeno. Subir resposta não é
apresentado como solução para essa classe. Seu F1 de localização também não
significa classificação correta: muitas anotações normais foram rotuladas2.

### LoG

Referência de construção: r3c18. Mantêm-se respostas0,08/0,12: com margem6,
elas recuperaram 17 e cinco pequenos, respectivamente. A menor resposta
conserva uma hipótese de sensibilidade à classe2, apesar do maior número de FP.

Margem5 interpola entre4 e6, buscando reduzir as caixas excessivas de
candidatos maiores. Entre os 644 normais perdidos com centro, 422 tinham
sigma maior que2; 279 dessas caixas excediam duas vezes a área anotada.
Por isso LoG testa5/6 enquanto DoG testa6/8. Não presumir uma margem universal.

### Parâmetros de escala preservados

Nos dois métodos: polaridade clara, sem pré-processamento, sigma mínimo2,
máximo solicitado12 e sobreposição0,5. LoG mantém dez escalas lineares;
DoG mantém razão1,6. Pequeno ≤π×4²; aglomerado ≥π×12².

A grade DoG termina em sigma8,192, abaixo da faixa necessária para prever
classe1 com a regra atual. Essa limitação permanece explícita; investigar
aglomerados exigirá outro contraste. A margem modifica somente a caixa,
preservando centro, sigma, diâmetro, área estimada e classe do candidato.

## Controles e orçamento

| Round4 | Configuração repetida | Valores |
|---|---|---|
| r4c02 | r3c05 | SBD área48/distância6/margem3 |
| r4c04 | r3c09 | SBD área64/distância6/margem3 |
| r4c07 | r3c24 | DoG resposta0,12/margem6 |
| r4c16 | r3c16 | LoG resposta0,08/margem6 |
| r4c18 | r3c18 | LoG resposta0,12/margem6 |

Os controles ficam em suas posições naturais nas grades, sem serem movidos
para o início. Ordem: SimpleBlob (área, margem), DoG (resposta, margem), LoG
(resposta, margem). IDs, referências e parâmetros completos são congelados.

Seed42 é registrada; as grades são determinísticas e não usam sorteio.
Os três planos anteriores, seus hashes e as identidades das configurações
vinculam a geração. Não há adaptação de parâmetros durante a execução.

Após esta preparação são 122 execuções de configuração nas quatro rodadas
(48+32+24+18), das quais109 distintas. O teto geral é122 distintas em até136
execuções. Restam até13 novas para as14 vagas do round5; pelo menos uma deverá
repetir uma configuração se todas forem usadas. O desenho dependerá do round4.

## Executar

Na raiz do projeto, no PowerShell:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round4
```

O executor usa [round4.json](../scripts/blobs/rodadas/round4.json) e salva
comparações, tabelas, ranking e PDF em `resultados/frame-to-frame/blobs/round4/`.
Cada tentativa cria novas pastas. Não é necessário repetir rodadas anteriores.
Acrescentar `--conferir` apenas confere plano, dependências, hashes e imagens,
sem detectar objetos nem criar resultados.

O PDF mantém quatro páginas: visão geral, cobertura/classificação, resultados
por vídeo e nove pares de margem (três SBD, quatro DoG, dois LoG). Seus deltas
são descritivos. A análise estatística por vídeo vem depois da execução.

## O que conferir depois

1. Integridade das3.204 avaliações e reprodução das cinco referências.
2. Igualdade dos candidatos brutos nos nove pares que variam somente a caixa.
3. Ganho de F1 com TP/FP/FN, cobertura0/2/1 e classificação separados.
4. Consistência por vídeo e interações área × margem ou resposta × margem,
   usando o bootstrap exploratório já adotado.
5. Se a resposta mais alta reduz FP à custa de perdas excessivas; se margens
   novas melhoram uma parte do painel e pioram outra.

F1 de indivíduos continua sendo o critério acordado. As análises não escolhem
finalistas, não usam os conjuntos reservados e não alteram anotações.
Após o round5, produzir o documento explicativo de blobs antes da seleção e vídeos.

## Arquivos desta preparação

Novo gerador interno `scripts/blobs/planejamento_round4.py`, plano
`scripts/blobs/rodadas/round4.json`, testes específicos do planejamento e do
executor. Ajustados o carregador de planos, executor, relatório e seus testes,
guias e estado da pesquisa. Os módulos dos detectores e os planos anteriores
permanecem preservados. O gerador é interno; o comando do usuário é o mesmo.

## Conferências da preparação

- **110 testes distintos aprovados:** 52 de planejamento, 34 de executor,
  24 do relatório, incluindo regressões das versões anteriores.
- Conferência real de18 configurações e178 pares de imagem/anotação aprovada,
  sem executar detectores ou criar resultados do round4. A cadeia verifica
  362 hashes de entradas/planos e arquiva24 arquivos de código na execução.
- Plano regenerado de forma idêntica no Python3.13.3; cinco repetições exatas,
  13 novas e109 distintas acumuladas. Planos round1/2/3 preservados.
- PDF sintético de quatro páginas renderizado e revisado, sem substituir
  PDFs reais. Os testes não medem o desempenho na base.

SHA-256 do plano congelado:
`f5d69b234435e2dfa64e681dc44eaac651fcf7a4eb9667a21e03a46ad62e154e`.
