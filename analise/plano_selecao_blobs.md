# Comparação das configurações de blobs em imagens de seleção

## Etapa e objetivo

As cinco rodadas de desenvolvimento terminaram. Esta etapa compara **todas as
119 configurações distintas** em um conjunto comum de imagens de seleção,
antes da escolha conjunta de cinco finalistas. Não é uma sexta rodada de
ajuste. O [documento do desenvolvimento](desenvolvimento_blobs.html) explica
as decisões e os resultados que produziram esse catálogo.

O conjunto e os critérios seguem o [protocolo acordado](plano_blobs.md):
**60 JPEGs dos vídeos 13, 29, 52 e 54**, com os quadros 0, 100, …, 1400
de cada vídeo. São **119 × 60 = 7.140 avaliações**. Os JPEGs e as anotações
são os mesmos do plano de seleção da limiarização, conferidos por SHA-256.
Anotação ausente impede a execução; um arquivo de anotação vazio é um caso
válido sem objetos anotados. Não há exclusões novas.

Essas imagens já foram usadas na limiarização e fazem parte do histórico da
pesquisa. A separação do desenvolvimento de blobs não as torna dados inéditos
para o projeto. Os resultados de seleção orientarão uma escolha e não devem
ser apresentados como avaliação final independente.

## Catálogo congelado e reprodução

O [plano executável](../scripts/blobs/selecao/plano.json) reúne as 136 posições
dos cinco planos, removendo 17 repetições sem descartar tentativas distintas:

| Método | Configurações distintas |
|---|---:|
| SimpleBlobDetector | 84 |
| DoG | 22 |
| LoG | 13 |
| Total | 119 |

A identidade considera método, pré-processamento, parâmetros, classificação
e adaptação de caixa. São preservadas as opções original, escala e margem,
assim como as variantes com CLAHE. A ordem da primeira aparição nos planos
define os IDs `s001` a `s119`; o registro de procedência permite recuperar
todos os IDs equivalentes das rodadas. Esses IDs não indicam qualidade.

O executor confere os planos e os registros dos cinco batches completos,
captura as imagens e anotações em memória e usa os mesmos bytes para todas
as configurações. O plano e as fontes de código ficam arquivados na execução,
com hashes, versões das dependências e parâmetros efetivos dos detectores.
Seed 42 fica registrada; não há sorteio nem mudança de parâmetros durante
a seleção. Reproduzir requer o mesmo plano, entradas, código e ambiente;
a seed sozinha não garante igualdade entre versões de bibliotecas.

As configurações com desempenho ruim no desenvolvimento também participam.
As 22 variantes DoG mantêm a limitação da faixa de escala que não alcança
o corte de aglomerado. Corrigi-la agora criaria configurações não avaliadas
no desenvolvimento. As quantidades diferentes de tentativas por método
também devem acompanhar a interpretação da comparação.

## Métricas e escolha posterior

- **Critério principal:** F1 de indivíduos, calculado após somar TP, FP e FN
  dos 60 frames: `2TP / (2TP + FP + FN)`.
- **Correspondência:** IoU ≥ 0,50; cada anotação e previsão participa de no
  máximo um par. Maximiza-se a quantidade de pares e depois a soma das IoUs.
- **Classes 0 e 2:** avaliadas juntas na localização. Trocas entre normal e
  pequeno contam como acerto de localização e erro de classificação separado.
- **Classe 1:** aglomerados são avaliados separadamente. Trocas entre esse
  grupo e indivíduos geram erros de detecção nos respectivos grupos.
- **Sem casos:** TP = FP = FN = 0 permanece indefinido. Quando existem
  somente perdas ou falsas detecções, F1 é zero.
- **Empates:** comparação pela fração exata das contagens, sem arredondamento,
  peso adicional ou desempate por classe 0. IDs apenas estabilizam a exibição.

Precisão, recall, cobertura das classes 0/2/1, erros condicionais de
classificação, F1 de aglomerados e resultados por vídeo acompanham o ranking.
Os frames de um vídeo não são observações independentes. A dispersão entre
configurações é descritiva; não demonstra significância estatística de uma
vantagem nem deve ser usada como intervalo de confiança da vencedora.

O relatório ajuda a revisar as cinco primeiras posições, mas não grava um
plano de finalistas automaticamente. Um empate que atravesse a quinta vaga
será destacado e exigirá decisão registrada. A cobertura de pequenos merece
atenção explícita, pois o F1 agregado dá mais influência aos objetos normais,
que são mais numerosos. Qualquer alteração do critério terá de ser discutida
e registrada, preservando a análise pelo critério atual.

## Executar

No PowerShell, na raiz do projeto, a conferência opcional não cria resultados:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_selecao.py" --conferir
```

Para executar a comparação completa e gerar o PDF:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_selecao.py"
```

O próprio comando completo repete a conferência antes de detectar. Não é
necessário reexecutar o desenvolvimento nem gerar novamente o plano.

## Saídas e leitura

Cada tentativa cria pastas novas sob `resultados/frame-to-frame/blobs/selecao/`:

```text
selecao/
  batch__<execucao>/
    plano.json
    execucao.json
    codigo.zip
    ranking.csv
    resumo_configuracoes.csv
    resumo_por_video.csv
    resumo_por_quadro.csv
    relatorio.json
    relatorios/<data-hora>/relatorio.pdf
  <id_metodo_preprocessamento_caixa_hash>__<execucao>/
    configuracao.json
    configuracao_backend.json
    execucao.json
    avaliacao.json
    resumo_por_quadro.csv
    quadros/<video>_frame_<numero>/
      comparacao.png
      anotacoes.csv
      deteccoes.csv
      predicoes.txt
      avaliacao.json
      pares.csv
      pendentes.csv
```

O nome identifica a configuração e a tentativa; o JSON contém todos os
parâmetros. SimpleBlobDetector também salva `configuracao_opencv.json`.
CLAHE acrescenta `preprocessamento.png`. As tabelas preservam as medidas
brutas dos blobs e as caixas originais/adaptadas. Não há rastreamento ou
identidade persistente entre frames.

Para comparar desempenho, abra o PDF indicado em `relatorio.json` e consulte
`ranking.csv`, coluna `f1_individuos`. Use a procedência do plano para relacionar
`sNNN` aos nomes usados nas cinco rodadas. Os painéis mostram anotações à
esquerda e detecções à direita sobre a imagem original.

Se apenas o PDF falhar, as métricas concluídas permanecem salvas. Feche o PDF
aberto e gere outro relatório, substituindo o caminho pelo batch desejado:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_selecao.py" --somente-relatorio ".\resultados\frame-to-frame\blobs\selecao\batch__<execucao>"
```

## Depois da execução

1. Conferir integridade, desempenho agregado, cobertura e diferenças entre
   os quatro vídeos; revisar visualmente os casos relevantes.
2. Escolher conjuntamente cinco configurações, registrando a decisão e
   preservando os parâmetros avaliados nesta seleção.
3. Preparar e executar as cinco nos vídeos completos 13, 29, 52 e 54.
4. Após revisão, congelar as mesmas cinco para os vídeos finais 14, 24, 38
   e 82, sem ajuste a partir dos resultados finais.

Os executores e planos de vídeo de blobs serão preparados nessas etapas.
Esta preparação não realiza o experimento de seleção nem escolhe finalistas.

## Implementação e conferência da preparação

| Arquivo | Mudança nesta etapa |
|---|---|
| [executar_selecao.py](../scripts/blobs/executar_selecao.py) | Novo comando para conferir, executar a seleção e regenerar seu PDF |
| [planejamento_selecao.py](../scripts/blobs/planejamento_selecao.py) e [plano.json](../scripts/blobs/selecao/plano.json) | Catálogo determinístico, procedência e entradas congeladas |
| [executar_rodada.py](../scripts/blobs/executar_rodada.py) | Núcleo compartilhado para manter as mesmas saídas; ranking pela fração exata das contagens |
| [relatorio_selecao_blobs.py](relatorio_selecao_blobs.py) | PDF específico da comparação, com todas as candidatas e aviso de empate na quinta vaga |
| [teste do plano](../scripts/testes/test_planejamento_selecao_blobs.py), [teste do executor](../scripts/testes/test_executar_selecao_blobs.py) e [teste do relatório](../scripts/testes/test_relatorio_selecao_blobs.py) | Testes sintéticos da nova etapa |
| [teste das rodadas](../scripts/testes/test_executar_rodada_blobs.py) | Fixture de ranking com as contagens usadas no cálculo exato |
| [README principal](../README.md), [guia de scripts](../scripts/README.md), [guia de blobs](../scripts/blobs/README.md), [guia de análise](README.md) e [estado da pesquisa](estado_pesquisa.md) | Comando atual e sequência após a execução |

A conferência do novo comando passou em Python 3.13.3: 119 configurações,
60 imagens/anotações e 7.140 avaliações previstas, sem criar resultados.
O plano foi regenerado de forma idêntica; as 136 origens e os cinco planos
históricos foram preservados. Passaram **88 testes**: 22 do planejador, 10 da
integração de seleção, 14 do relatório e 42 de regressão do executor das rodadas.
O PDF sintético teve suas sete páginas renderizadas e conferidas visualmente;
o contrato de suas tabelas foi comparado às saídas do executor em JPEG sintético.
Essas verificações avaliam a infraestrutura, não o desempenho na seleção.
