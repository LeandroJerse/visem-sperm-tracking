# Blobs: cinco configurações nos vídeos completos de seleção

## Decisão e escopo

Após a análise da seleção em imagens, foram aprovadas **s052, s082, s084,
s103 e s051**, nessa ordem, para os vídeos completos **13, 29, 52 e 54**.
O [plano congelado](../scripts/blobs/videos/plano_selecao.json) preserva
integralmente os detectores, parâmetros, pré-processamento, caixas e classes
das cinco configurações. Nenhum parâmetro é ajustado durante a execução.

Esta etapa foi concluída em `batch__20260921T022547636341Z` e está
[conferida e analisada](analise_videos_selecao_blobs.md). Ela amplia a
cobertura temporal dos vídeos já usados na seleção em imagens; não constitui
uma avaliação final independente. Os vídeos finais 14, 24, 38 e 82 ficam
para a etapa posterior, após revisar estes resultados.

| Configuração | Detector | Diferença principal | Caixa |
|---|---|---|---|
| s052 | SimpleBlobDetector | Área mínima 32; distância 12 | Margem 6 px |
| s082 | SimpleBlobDetector | Área mínima 64; distância 6 | Margem 4 px |
| s084 | SimpleBlobDetector | Área mínima 64; distância 12 | Margem 4 px |
| s103 | DoG | Resposta mínima 0,16; sigma solicitado 2–12 | Margem 8 px |
| s051 | SimpleBlobDetector | Área mínima 32; distância 12 | Margem 5 px |

Todas usam polaridade clara e nenhum pré-processamento. A tabela resume as
diferenças; os valores completos e suas origens constam do plano. A
[análise da seleção](analise_selecao_blobs.md) registra os limites de cobertura
de pequenos e aglomerados, a semelhança entre s082/s084 e os erros de
classificação de s103. A aprovação não elimina essas limitações.

| Vídeo | Frames, começando em zero | FPS | Resolução |
|---|---|---|---|
| 13 | 1.470 | 49 | 640 × 480 |
| 29 | 1.470 | 49 | 640 × 480 |
| 52 | 1.440 | 48 | 640 × 480 |
| 54 | 1.470 | 49 | 640 × 480 |

São **5.850 frames por configuração**, **29.250 avaliações** e **20 MP4
comparativos**. O detector funciona quadro a quadro, sem rastreamento.

## Executar

Para reproduzir a etapa concluída, na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_videos.py" --etapa selecao
```

Não é necessário repetir rodadas ou seleção em imagens. Opcionalmente,
acrescente `--conferir` para verificar plano, arquivos, anotações, dependências
e metadados dos MP4 sem percorrer os frames, detectar objetos ou criar
resultados. A conferência completa do alinhamento ocorre na execução.

## Conferências antes e durante a execução

1. Conferir o plano, as 22 fontes de procedência, os quatro MP4, as 5.850
   anotações e as 20 imagens de referência pelos hashes registrados.
   Conferir também bibliotecas, parâmetros e metadados dos contêineres.
2. Decodificar cada vídeo completo antes da primeira detecção, verificando
   dimensões, número de frames e correspondência temporal. Para cada vídeo,
   as imagens de referência dos frames 0, 100, 700, 1400 e último precisam
   corresponder ao mínimo único do erro absoluto médio entre todos os frames.
   A comparação admite diferenças de compressão JPEG/MP4; não exige pixels
   iguais entre esses formatos e não corrige deslocamentos automaticamente.
3. Registrar o hash dos pixels de cada frame decodificado. As cinco
   configurações devem receber exatamente esses mesmos pixels e anotações.
4. Aplicar a mesma sequência da avaliação em imagens: pré-processamento,
   detector, adaptação da caixa e avaliação. Centro, diâmetro, área circular,
   caixa original e caixa adaptada permanecem registrados separadamente.
5. Gravar os MP4 com anotações à esquerda e detecções à direita. Reabrir
   cada saída e decodificá-la por completo para conferir contagem, FPS e
   dimensões. O painel tem 1280 × 584 pixels e conserva o FPS do original.
6. Recalcular as métricas agregadas, conferir novamente as fontes,
   registrar hashes das saídas e gerar o PDF.

Anotação ausente, origem alterada, sequência incompleta, alinhamento ambíguo
ou vídeo de saída inválido interrompem a execução. A tentativa incompleta
fica identificada como falha e é preservada. Repetir o comando cria outra
pasta; não retoma silenciosamente nem sobrescreve a tentativa anterior.

## Métricas e dados

O critério permanece **F1 de localização de indivíduos**, reunindo classes
0 e 2. O pareamento é um para um, com IoU ≥ 0,5: maximiza o número de pares
e depois a soma das sobreposições. Trocar 0 por 2 mantém o acerto de
localização e registra erro de classificação. A classe 1 é avaliada
separadamente; trocar entre indivíduo e aglomerado gera perda e falsa
detecção nos respectivos grupos.

Os totais somam TP, FP e FN antes de calcular F1. Empates exatos permanecem
empatados; ID apenas organiza sua apresentação. Cobertura das classes,
classificação entre pares, precisão, recall e resultados por vídeo
acompanham o ranking. Sem anotações nem previsões, a métrica fica sem casos;
previsões sem anotações contam como falsos positivos.

O tempo do frame é `quadro / FPS`, relativo ao início do clipe. As tabelas
registram posição e tamanho em pixels, coordenadas normalizadas e tempos de
pré-processamento, detector, adaptação e pipeline em nanossegundos.
Esses tempos não incluem leitura do vídeo, avaliação ou gravação das saídas.
O índice da detecção vale somente dentro do frame: as contagens representam
ocorrências por quadro, não indivíduos únicos nem trajetórias.

## Saídas e relatório

```text
resultados/videos/blobs/selecao/batch__<execucao>/
  plano.json, execucao.json, codigo.zip
  origens/                     cópias dos 22 arquivos de procedência
  conferencia/                 alinhamento, comparações e hashes dos frames
  ranking.csv
  resumo_configuracoes.csv      cinco totais
  resumo_por_video.csv          vinte resultados
  <configuracao>__<execucao>/
    configuracao.json, configuracao_backend.json, execucao.json
    deteccoes.csv, anotacoes.csv, por_quadro.csv, pares.csv, pendentes.csv
    avaliacao.json, resumo.csv, resumo_por_video.csv
    midia/<id>__cfg-<hash>__video-<numero>.mp4
  relatorios/<execucao-relatorio>/relatorio.pdf
  relatorio.json                indicação do PDF ou da falha do relatório
```

As pastas identificam ID, método, pré-processamento, polaridade, margem e
hash da configuração. O nome curto dos MP4 evita caminhos excessivos no
Windows. Parâmetros completos, versões e código usado acompanham o batch.
Seed 42 permanece registrada, sem sorteio durante a execução; tempos e
bytes dos vídeos/PDFs podem variar conforme ambiente e bibliotecas.

O PDF reúne F1/precisão/recall, contagens e cobertura, classificação,
diferenças por vídeo e tempos. A geração confere a consistência das tabelas
por frame com seus totais e a integridade das mídias. Uma falha apenas no
PDF não invalida vídeos e métricas concluídos. Para gerar outro relatório:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_videos.py" --somente-relatorio ".\resultados\videos\blobs\selecao\batch__<execucao>"
```

Após executar, conferir integridade, revisar as vinte comparações e analisar
os resultados juntos. O passo seguinte do protocolo é congelar as mesmas
cinco configurações para os vídeos finais, preservando parâmetros e métricas
e registrando o histórico de exposição dos dados.

As novas execuções guardam as fontes em `origens/`. O leitor do relatório
também reconhece o formato anterior, com fontes na raiz. A reorganização
de uma execução concluída preserva o manifesto anterior e o mapa dos caminhos
em `origens/historico_organizacao/`; PDFs históricos conservam seus bytes,
seus registros e os caminhos válidos no momento em que foram produzidos.

## Registro da preparação

Passaram **96 testes**: 19 do plano, 15 do executor, 13 do relatório e 49
de regressão dos utilitários de vídeo. Foram conferidos gravação e leitura
integral de MP4s sintéticos, correspondência com a cadeia de imagens,
classes e caixas, métricas, tempos, falhas de alinhamento e integridade.
O PDF sintético de quatro páginas foi renderizado e revisado.

A conferência `--conferir` do plano real passou com as cinco configurações,
quatro MP4, 5.850 anotações, 20 JPEGs e 22 fontes. Não houve detecção nem
decodificação de frames reais, e nenhuma pasta de resultados de vídeo de
blobs foi criada. O plano foi reproduzido com bytes idênticos em Python 3.13.3.

SHA256 do plano: `cc36923b5a846023e8ee538ea25a8e1ce09791a7ee5f798310165749b512b8ed`.
Os sete planos anteriores e a configuração pessoal de limiarização foram
preservados. O alinhamento real permanece para a execução do pesquisador.

Arquivos desta preparação:

- `scripts/blobs/executar_videos.py`, `planejamento_videos.py` e
  `videos/plano_selecao.json`: execução e plano congelado.
- `analise/relatorio_videos_blobs.py`: PDF automático e conferência dos resultados.
- `scripts/testes/test_planejamento_videos_blobs.py`, `test_videos_blobs.py`
  e `test_relatorio_videos_blobs.py`: testes sintéticos.
- Este plano, registro de aprovação na análise da seleção, estado da pesquisa
  e guias principal, de scripts, de blobs e de análise: comando e situação atual.
