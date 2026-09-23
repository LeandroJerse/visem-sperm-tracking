# Blobs: avaliação final em vídeos

Execução concluída em `batch__20260921T034832637647Z` e conferida em
21/09/2026. A [conclusão](conclusao_blobs.md) registra os resultados e limites.
Este documento preserva o planejamento anterior à execução; os comandos
servem para reprodução.

## Decisão aprovada

Após a [conferência dos vídeos de seleção](analise_videos_selecao_blobs.md),
foi aprovada a preparação da avaliação final nos vídeos **14, 24, 38 e 82**,
mantendo **s052, s082, s084, s103 e s051**, nessa ordem. Não há ajuste de
detector, pré-processamento, parâmetros, caixas, limites de classe ou métricas.

O [plano final congelado](../scripts/blobs/videos/plano_final.json) contém
as cinco configurações completas e a identidade de cada fonte. O experimento
será executado pelo pesquisador. O executor é o mesmo da seleção; a opção
`--etapa final` escolhe o plano e a pasta de resultados correspondentes.

| Vídeo | Frames, com índice inicial zero | FPS | Resolução |
|---|---:|---:|---|
| 14 | 1.470 | 49 | 640 × 480 |
| 24 | 1.470 | 49 | 640 × 480 |
| 38 | 1.470 | 49 | 640 × 480 |
| 82 | 1.500 | 50 | 640 × 480 |

São **5.910 frames por configuração**, **29.550 avaliações** e **20 vídeos
comparativos**. A representação continua compatível com as anotações da base.

## Executar

No PowerShell, na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_videos.py" --etapa final
```

Não é necessário repetir desenvolvimento ou seleção. Para conferir somente
plano, origens, anotações, dependências e metadados dos MP4, acrescente
`--conferir`. Essa opção não decodifica frames, executa detecções ou cria
resultados. A verificação completa do alinhamento ocorre na execução.

## Mesmas regras, outra partição

Cada configuração recebe todos os frames e as mesmas anotações. Antes da
primeira detecção, o executor confere a sequência completa e seu alinhamento
com cinco JPEGs de referência por vídeo (frames 0, 100, 700, 1400 e último).
Hashes dos pixels garantem a mesma entrada para as cinco configurações.
Anotações ausentes, hashes divergentes, frames incompletos ou alinhamento
ambíguo interrompem a tentativa, preservando seu registro.

O critério principal permanece **F1 de localização de indivíduos (0 e 2)**,
somando TP, FP e FN antes do cálculo. Pareamento um a um com IoU ≥ 0,5;
trocas entre 0 e 2 contam como localização correta e erro de classificação
separado. Aglomerados (1) são avaliados à parte. Cobertura por classe,
precisão, recall, classificação condicional e resultados por vídeo acompanham
o ranking. Empates exatos são preservados; não há ajuste de pesos ou de
parâmetros em resposta ao resultado final.

Os limites observados na seleção, especialmente para pequenos e aglomerados,
fazem parte dos resultados do método. O histórico de uso anterior da base
permanece registrado: a separação atual não transforma os dados em inéditos.
Frames consecutivos não são amostras independentes. Não há rastreamento,
contagem de indivíduos únicos, velocidade ou comportamento nesta etapa.

O plano usa **43 fontes de procedência**: as 22 da seleção em imagens,
o plano e os registros dos vídeos de seleção, os registros das cinco
configurações executadas e a especificação dos vídeos finais. Da limiarização
são reutilizados apenas os arquivos, anotações, metadados e referências de
alinhamento; suas configurações ou resultados não selecionam candidatos de blobs.

## Organização das saídas

```text
resultados/videos/blobs/final/batch__<execucao>/
  plano.json, execucao.json, codigo.zip
  ranking.csv, resumo_configuracoes.csv, resumo_por_video.csv
  relatorio.json
  origens/                         43 cópias de procedência
  conferencia/                     alinhamento e hashes dos frames
  relatorios/<execucao-relatorio>/relatorio.pdf
  <configuracao>__<execucao>/
    configuracao.json, configuracao_backend.json, execucao.json
    deteccoes.csv, anotacoes.csv, por_quadro.csv, pares.csv, pendentes.csv
    avaliacao.json, resumo.csv, resumo_por_video.csv
    midia/<id>__cfg-<hash>__video-<numero>.mp4
```

Cada MP4 mostra as anotações à esquerda e as detecções à direita, com o FPS
original e painel de 1280 × 584 pixels. Os vinte arquivos são reabertos e
decodificados integralmente para conferir contagem, dimensões e FPS. O PDF
automático de quatro páginas identifica a etapa final e reúne desempenho,
cobertura/classificação, diferenças entre vídeos e tempos.

Cada execução cria outro batch. Uma falha apenas na geração do PDF não
desfaz as métricas ou vídeos concluídos. Para gerar outro relatório:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_videos.py" --somente-relatorio ".\resultados\videos\blobs\final\batch__<execucao>"
```

O comando de seleção continua disponível para reprodução com `--etapa selecao`.
Após a execução final, conferir integridade e analisar os resultados sem
ajustar os parâmetros nesses vídeos. A comparação com a limiarização deve
usar as mesmas métricas e os mesmos vídeos finais.

## Conferência da preparação

Passaram **58 testes**: 14 do planejador final, 22 do executor e 22 do
relatório. Cobrem preservação das configurações, separação das partições,
exportação de MP4s sintéticos, métricas, hashes, falhas e compatibilidade
com a seleção. O PDF final sintético teve suas quatro páginas renderizadas
e revisadas; nenhum PDF histórico foi alterado.

O comando `--etapa final --conferir` passou em Python 3.13.3: cinco
configurações, quatro MP4s, 5.910 anotações e vinte JPEGs de referência,
com 43 fontes de procedência verificadas. A conferência leu bytes e metadados;
não decodificou frames reais, executou detecção ou criou resultados finais.
O alinhamento completo permanece para a execução do pesquisador.

Os doze arquivos de algoritmos e métricas envolvidos foram comparados com
o código arquivado na seleção em vídeos e permanecem idênticos. O plano
e o gerador da seleção, a configuração pessoal de limiarização e os
resultados históricos foram preservados. O leitor do relatório também
conferiu o batch real de seleção depois da generalização para a etapa final.

SHA256 do plano final:
`6a379cd2557906336ef2558aa472c207fb897f37dbec9101699e22f38ae218b7`.

SHA256 do gerador:
`4ecb012411699f3027d3a83549a46b8b760cdd1d5b5cf6ca49f4997acab0a88c`.

Arquivos desta preparação:

- `scripts/blobs/planejamento_videos_final.py` e `videos/plano_final.json`:
  contrato e plano congelado dos vídeos finais.
- `scripts/blobs/executar_videos.py`: seleção de etapa, plano e pasta;
  detecção, caixas e métricas mantidas.
- `analise/relatorio_videos_blobs.py`: conferência e PDF específicos de cada etapa.
- `scripts/testes/test_planejamento_videos_final_blobs.py`, `test_videos_blobs.py`
  e `test_relatorio_videos_blobs.py`: validação do plano, integração e relatório.
- Este plano, registro de continuidade na análise da seleção, estado da
  pesquisa e guias principal, de scripts, de blobs e de análise: comando atual.
