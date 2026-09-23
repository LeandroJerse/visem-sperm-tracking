# Blobs — desenho aprovado e preparação do round3

20/09/2026. **Desenho aprovado, executado e analisado.** Este documento
preserva a preparação; veja a [análise dos resultados](analise_round3_blobs.md)
e o [próximo round](plano_round4_blobs.md).
Base: [análise do round2](analise_round2_blobs.md) e
[estatísticas reproduzíveis](estatisticas_round2_blobs.json).

## Objetivo e modelo experimental

Testar combinações de poucos fatores com todas as combinações previstas
dentro de cada bloco. Esse desenho fatorial permite comparar um fator mantendo
os outros fixos e verificar **interações**: por exemplo, se aumentar a área
mínima ajuda somente quando a distância é menor.

O motivo é o resultado do round2: área 48 e distância 6 melhoraram separadamente
o F1, mas isso não garante que a combinação das duas alterações melhorará.
Da mesma forma, aumentar a margem pode ajudar um candidato verdadeiro e
prejudicar outro; a interação com a resposta precisa ser medida.
A [referência do NIST sobre planejamento experimental](https://www.itl.nist.gov/div898/handbook/pri/section3/pri3.htm)
fundamenta a escolha de desenhos com fatores e interações explícitos.

Não haverá nova métrica de ranking, treino de IA ou seleção de finalistas.
Continuam os mesmos 178 quadros de desenvolvimento, IoU≥0,50, indivíduos
0/2 juntos, aglomerados separados e F1 das contagens somadas. Cobertura de
pequenos, classificação e diferenças por vídeo permanecem visíveis.

## Bloco A — SimpleBlobDetector: 12 configurações

Base: r2c01, a repetição de r1c29. Cruzar:

| Fator | Valores | Justificativa |
|---|---|---|
| Área mínima interna | 32, 48, 64 | Explorar a região entre a referência e uma filtragem um pouco mais restritiva |
| Distância mínima | 6, 12 | O valor 6 melhorou oito vídeos e empatou quatro |
| Margem da caixa | 3, 4 | Faixa próxima da melhor geometria atual, sem expandir indiscriminadamente |

Total: **3 × 2 × 2 = 12**, incluindo quatro referências já avaliadas:

| Área mínima | Distância | Margem 3 | Margem 4 |
|---:|---:|---|---|
| 32 | 6 | Nova | Repetição r2c14 |
| 32 | 12 | Repetição r2c06 | Repetição r2c01 |
| 48 | 6 | Nova | Nova |
| 48 | 12 | Nova | Repetição r2c11 |
| 64 | 6 | Nova | Nova |
| 64 | 12 | Nova | Nova |

Todos os demais valores permanecem fixos: polaridade clara, sem CLAHE,
limiares 80–220 (máximo exclusivo), passo 5, repetibilidade 2, área máxima
500, inércia mínima 0,4, circularidade e convexidade desligadas.
A classificação mantém pequeno ≤π×3² e aglomerado ≥π×12² sobre a área
circular estimada. A margem não altera essa medida nem a classe.

O valor 64 é uma exploração acima de 48, não uma estimativa de ótimo.
O aumento de área já perdeu acertos no round2; não assumir que maior é melhor.
Área e distância serão avaliadas também por recall e cobertura de cada classe.

## Bloco B — LoG/DoG: 12 configurações

Em cada método, cruzar três respostas e duas margens:

| Método | Resposta | Margem | Quantidade |
|---|---|---|---:|
| LoG | 0,05; 0,08; 0,12 | 4 ou 6 pixels | 6 |
| DoG | 0,05; 0,08; 0,12 | 4 ou 6 pixels | 6 |

Todas são configurações novas. O limiar 0,05 liga o desenho ao round2;
0,08 e 0,12 sondam uma região mais restritiva depois da grande redução
de FP entre 0,02 e 0,05. São hipóteses, não valores obtidos de um modelo
que garanta preservar os acertos. A resposta não é probabilidade de confiança.

Margens 4 e 6 têm justificativa geométrica: em muitos pequenos, sigma 2
produziu caixas de aproximadamente 10×10 com margem 2, enquanto a referência
anotada tem medianas de 19×17. As novas margens produzem aproximadamente
14×14 e 18×18, permitindo verificar insuficiência e excesso. Não aumentar
a área circular usada na classificação junto com a caixa.

Manter: polaridade clara, sem CLAHE, sigma mínimo 2, máximo solicitado 12,
sobreposição 0,5. LoG mantém dez escalas lineares; DoG mantém razão 1,6.
Os limites de classificação continuam pequeno ≤π×4² e aglomerado ≥π×12².

**Limitação preservada:** a grade DoG atual termina em sigma 8,192 e não
alcança diâmetro 24, portanto não prevê classe 1 nessa faixa. O round3
proposto isola resposta e geometria para indivíduos. A ampliação de sigma
para investigar aglomerados deverá ser uma comparação separada; não está
incluída silenciosamente neste bloco.

Não diminuir sigma mínimo nesta rodada: sigma 2 já concentra muitos
candidatos espúrios, mas também candidatos próximos de pequenos. Antes de
descartá-lo ou acrescentar escalas menores, testar resposta e caixa.

## O que será possível comparar

- **Efeito de área:** comparar 32/48/64 com distância e margem iguais.
- **Efeito de distância:** comparar 6/12 em cada área e margem.
- **Efeito de caixa:** comparar margens com o mesmo detector e parâmetros.
- **Efeito de resposta:** comparar 0,05/0,08/0,12 com a mesma margem e método.
- **Interações:** verificar se o efeito de um fator muda conforme o outro.
  Por exemplo, ΔF1 da margem 6 versus 4 em cada limiar de resposta.

Usar diferenças pareadas por vídeo, contagens agregadas, cobertura por classe
e o mesmo bootstrap exploratório por vídeo utilizado na análise do round2.
Não aplicar ANOVA automaticamente aos 178 frames como se fossem independentes,
nem substituir o F1 oficial por média de F1 de frames ou vídeos.

Ao comparar as configurações com resposta 0,05 à margem 2 histórica do
round2, primeiro conferir igualdade de entradas, versões, parâmetros efetivos
e candidatos brutos por quadro: índice, centro, sigma, diâmetro, área estimada
e classe. Se houver divergência, não atribuir a diferença somente à caixa.
Essas configurações novas não devem ser rotuladas como controles repetidos.

## Orçamento e preparação

**24 configurações × 178 quadros = 4.272 avaliações.**

- Quatro repetições e 20 configurações novas.
- 76 configurações distintas anteriores + 20 = **96 distintas** acumuladas.
- Permanecem os limites de 18 configurações no round4, 14 no round5 e
  até 122 distintas no total. Chegar a 122 não é uma obrigação.
- Restam até 26 configurações novas; se forem usadas todas as 32 vagas
  dos dois últimos rounds, pelo menos seis precisarão ser repetições.

Não incluir CLAHE, nova polaridade, fusão de detectores ou k-NN no round3.
O CLAHE piorou as oito comparações atuais, e novas frentes diluiriam os
testes necessários para interpretar candidatos e caixas. Isso não encerra
definitivamente essas hipóteses; delimita a rodada proposta.

O plano executável está em [round3.json](../scripts/blobs/rodadas/round3.json).
O gerador interno [planejamento_round3.py](../scripts/blobs/planejamento_round3.py)
reconstrói a grade a partir dos bytes dos planos anteriores; o comando de
execução permanece o mesmo. Seed 42 é registrada, mas esta grade fixa não
usa sorteio. A ordem é área, distância e margem no SimpleBlob, depois método,
resposta e margem em LoG/DoG.

As repetições ficam em r3c02→r2c14, r3c03→r2c06, r3c04→r2c01 e
r3c08→r2c11, sem reuni-las artificialmente no início. Referências exploratórias:
r2c01 para SimpleBlob, r2c28 para LoG e r2c32 para DoG.

A preparação inclui:

1. Congelar o plano com fontes/hash, parâmetros completos, ordem e referências,
   preservando os planos anteriores e validando identidades e orçamento.
2. Atualizar a leitura de planos, a conferência e o PDF para o novo desenho,
   com regressões sintéticas e sem executar a base.
3. Conferir as 178 entradas, deixando a execução real para o pesquisador.
4. Preservar no PDF as métricas e mostrar 12 comparações que diferem somente
   na margem. Área, distância, resposta e interações serão analisadas após a execução.

Para executar, na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round3
```

Saídas: `resultados/frame-to-frame/blobs/round3/`. Acrescentar `--conferir`
apenas valida plano, dependências e as entradas, sem detecção nem resultados.
Depois do round3, analisar resultados antes de definir round4 e round5.

## Conferências da preparação

- Releitura das quatro fontes da análise: hashes preservados, 32 configurações,
  384 resumos por vídeo e F1 consistente com as contagens agregadas.
- Grade com 24 identidades únicas, quatro repetições exatas e 96 distintas
  acumuladas; os bytes dos planos round1 e round2 foram preservados.
- Conferência real das dependências e dos 178 pares imagem/anotação aprovada,
  sem detectar objetos nem criar a pasta de resultados do round3.
- Testes sintéticos cobrem geração, orçamento, cadeia de hashes, falhas de
  origem, exportação dos três métodos e compatibilidade com planos anteriores.
  Passaram **85 testes distintos**: 38 de planejamento, 27 do executor e
  20 do relatório. Também foi conferida a regeneração idêntica do plano
  congelado no Python 3.13.3.
- PDF sintético de quatro páginas renderizado e revisado; nenhum PDF de
  resultado real foi substituído. As métricas de teste não são resultados do round3.

Arquivos principais preparados ou ajustados:

| Arquivo | Responsabilidade |
|---|---|
| [planejamento_round3.py](../scripts/blobs/planejamento_round3.py) | Gerar a grade e conferir sua ligação com os planos anteriores |
| [round3.json](../scripts/blobs/rodadas/round3.json) | Congelar parâmetros, referências, ordem e fontes |
| [planejamento.py](../scripts/blobs/planejamento.py) | Aceitar o novo contrato sem mudar as identidades antigas |
| [executar_rodada.py](../scripts/blobs/executar_rodada.py) | Conferir e arquivar a cadeia de origens do round3 |
| [relatorio_rodada_blobs.py](relatorio_rodada_blobs.py) | Ler o round3 e apresentar os pares de margem no PDF |
| [test_planejamento_round3_blobs.py](../scripts/testes/test_planejamento_round3_blobs.py), [test_executar_round3_blobs.py](../scripts/testes/test_executar_round3_blobs.py), [test_relatorio_rodada_blobs.py](../scripts/testes/test_relatorio_rodada_blobs.py) | Verificar o plano, a integração e o relatório com dados sintéticos |

Os guias e a [síntese de continuidade](estado_pesquisa.md) foram atualizados
para apontar o comando do round3 e distinguir preparação de execução.

SHA-256 do plano congelado:
`1b362082bd1fa22b2885a8b3f898c5116c2a34f4915de8c3f7cf374a457bce46`.

O documento explicativo completo de blobs permanece previsto após o round5,
antes da seleção em outras imagens e dos vídeos. Não reiniciar as rodadas.
