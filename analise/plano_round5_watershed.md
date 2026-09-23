# Watershed — plano do round5

21/09/2026. Combinações aprovadas após a [análise do round4](analise_round4_watershed.md).
Plano executável: [round5.json](../scripts/watershed/rodadas/round5.json).
**Preparado; a execução real fica com o pesquisador.**

## Objetivo e evidências

Comparar **14 configurações × 178 quadros = 2.492 avaliações**: seis controles
e oito combinações novas, em sete pares separar/preservar por área.
Ao concluir a rodada, serão **114 configurações distintas** nos cinco rounds.
O orçamento fecha o desenvolvimento; a seleção em outras imagens vem depois.

A líder r4c16 alcançou F1 de indivíduos 0,481308, contra 0,478007 da referência
anterior. Semente 0,50, Otsu −3 e fechamento 3×3 melhoraram seus contrastes nas
duas políticas, mas os ganhos variaram entre vídeos. A área mínima 144 reduziu
falsos positivos com perda de cobertura. Otsu −7 piorou e não foi ampliado.
Essas evidências orientam as combinações; seus ganhos não podem ser somados
como se os ajustes fossem independentes.

## Configurações congeladas

IDs ímpares usam **separar**; pares usam **preservar por área**.

| Par | IDs | Ajuste Otsu | Semente | Área mínima | Fechamento | Papel |
|---|---|---:|---:|---:|---:|---|
| p01 | r5c01/r5c02 | −5 | 0,50 | 120 | 5×5 | Controles r4c15/r4c16 |
| p02 | r5c03/r5c04 | −3 | 0,35 | 120 | 5×5 | Controles r4c07/r4c08 |
| p03 | r5c05/r5c06 | −5 | 0,35 | 120 | 3×3 | Controles r4c17/r4c18 |
| p04 | r5c07/r5c08 | −3 | 0,50 | 120 | 5×5 | Limiar e semente |
| p05 | r5c09/r5c10 | −5 | 0,50 | 120 | 3×3 | Fechamento e semente |
| p06 | r5c11/r5c12 | −3 | 0,50 | 120 | 3×3 | Os três ajustes |
| p07 | r5c13/r5c14 | −5 | 0,50 | 144 | 5×5 | Área maior com semente 0,50 |

Os controles representam referências e hipóteses, sem antecipar finalistas.
O JSON fixa todos os parâmetros, as imagens e suas origens. Seed 42 permanece
registrada; a grade é dirigida e determinística, sem sorteio.

## Comparações que isolam os ajustes

Cada linha abaixo gera duas comparações, uma por política: **14 contrastes**.
Não são 14 configurações novas. Os oito resultados novos são reaproveitados
nas comparações com referências diferentes.

| Referência → combinação | Único parâmetro alterado |
|---|---|
| p01 → p04 | Otsu −5 → −3 |
| p02 → p04 | Semente 0,35 → 0,50 |
| p01 → p05 | Fechamento 5 → 3 |
| p03 → p05 | Semente 0,35 → 0,50 |
| p04 → p06 | Fechamento 5 → 3 |
| p05 → p06 | Otsu −5 → −3 |
| p01 → p07 | Área mínima 120 → 144 |

p01/p04/p05/p06 formam o cruzamento Otsu −5/−3 × fechamento 5/3,
mantendo semente 0,50 e mínimo 120. Assim, o fechamento pode ser comparado
em cada limiar, e o limiar em cada fechamento. p06 é comparado com p04 e
p05; compará-lo somente com p01 confundiria duas mudanças.
Os campos `contrastes` e `contraste_com` registram essas referências.

O PDF apresenta F1, diferenças de TP/FP/FN e cobertura de pequenos, mantendo
as páginas de variação por vídeo e classificação. São comparações descritivas;
quadros do mesmo vídeo são correlacionados e essas diferenças não demonstram
significância estatística. Na análise posterior, conferir também a estabilidade
entre vídeos, sem declarar uma melhoria apenas pelo resultado agregado.

## Parâmetros e critérios preservados

- Otsu claro, imagem original, abertura desligada, fechamento retangular com
  uma iteração, conectividade 8 e área máxima 5.000 pixels.
- Pequeno até 120 pixels; aglomerado a partir de 900. Com mínimo 120,
  apenas regiões de exatamente 120 pixels podem receber classe 2.
  Mínimo 144 impede emitir classe 2. Isso não impede localizar um pequeno
  como normal, mas a troca de classe continua registrada.
- Caixas envolvem as regiões segmentadas. Detector, classificação, escritor
  de saídas e avaliador permanecem iguais aos do round4.
- Mesmos 178 quadros de desenvolvimento; exclusões 23/900 e 23/1100.
  A preparação não usa imagens reservadas para seleção nem vídeos finais.
- F1 de localização de indivíduos 0+2; aglomerados separados. IoU ≥ 0,50,
  pareamento exclusivo, maximização do número de pares e depois das IoUs.
  Trocas 0/2 são acertos de localização com erro de classificação separado.
- Somar contagens antes do F1; “sem casos” somente sem TP, FP e FN.
  Empates exatos compartilham posição; classe 0 não recebe peso de desempate.

A cobertura de pequenos segue sendo uma limitação: a líder do round4
localizou 10/134, todos previstos como normal. Este plano verifica combinações
das melhorias observadas; não promete resolver a classificação nem as perdas
de localização apenas ajustando os limites de área.

## Executar

Na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round5
```

Conferir somente entradas, referências e dependências, sem detecção:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round5 --conferir
```

Recuperar somente o PDF após as métricas concluírem:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round5 --somente-relatorio "CAMINHO_COMPLETO_DO_BATCH"
```

Saídas em `resultados/frame-to-frame/watershed/round5/batch__<UTC>/`, com
pastas por configuração/quadro, imagens comparativas, máscaras, mapas,
caixas, avaliações, metadados e tabelas. O **PDF automático tem cinco páginas**;
a última apresenta os 14 contrastes, com F1 e diferenças em seis casas.
O caminho aparece no terminal e no `relatorio.json` do batch.

Cada tentativa cria uma pasta nova, preservando anteriores. Interrupções
preservam parciais; não existe retomada automática. Falha no PDF preserva
as métricas e permite recuperação por `--somente-relatorio`.

## Reprodução e conferências

Os seis controles repetem **1.068 casos**, comparando **4.272 arquivos**
com o round4: `predicoes.txt`, `deteccoes.csv`, `avaliacao.json` e
`diagnostico.json`. Tempos e títulos de imagens não entram na identidade.
Divergência interrompe o batch e preserva os arquivos para diagnóstico.

A conferência sem detecção validou **4.636 origens**, incluindo plano,
análise, arquivos históricos, controles e 178 imagens com suas anotações.
O gerador reproduz exatamente o JSON existente ou recusa sobrescrevê-lo.
Não é necessário executá-lo antes do batch já preparado.

`codigo.zip` arquivará **38 fontes**; a versão anterior fica em
`origens/round4_codigo.zip`. Conserve esses arquivos e as rodadas anteriores.
Somente o comando e o relatório compartilhados foram estendidos.
As cinco páginas de uma prévia fictícia foram conferidas visualmente.
Passaram **79 testes sintéticos**: 67 anteriores e 12 novos, cobrindo
plano, contrastes de um parâmetro, execução, controles, interrupções,
integridade, preservação das métricas e recuperação do PDF.
O gerador reproduziu o plano byte a byte; a matriz coincide com a proposta
aprovada e a contagem de configurações distintas foi conferida.
Testes técnicos e conferência de entradas não demonstram melhora experimental.

## Arquivos desta preparação

| Função | Arquivos |
|---|---|
| Plano | `scripts/watershed/planejamento_round5.py`, `scripts/watershed/rodadas/round5.json` |
| Execução | `scripts/watershed/execucao_round5.py`, extensão de `scripts/watershed/executar_rodada.py` |
| PDF | `analise/relatorio_round5_watershed.py`, extensão de `analise/relatorio_rodada_watershed.py` |
| Testes | `scripts/testes/test_round5_watershed.py` |
| Documentação | Este plano, estado da pesquisa e guias principais |

Após a execução, conferir integridade, controles, resultados por vídeo e
limitações, e encerrar a análise das cinco rodadas. A próxima etapa do protocolo
é comparar as configurações distintas nos 60 quadros de seleção, revisar as
cinco finalistas e só então preparar os vídeos completos. Essa seleção ainda
não foi preparada nem executada nesta etapa.
