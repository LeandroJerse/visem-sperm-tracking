# Inspeção e diagnóstico de blobs

O round0 foi executado em `inspecao__20260920T041252237886Z`: 12 avaliações
concluídas, com arquivos íntegros, mas localização insuficiente. O próximo
passo é diagnosticar candidatos, delimitação e classificação antes do round1.
O [plano completo dos próximos testes](../../analise/plano_diagnostico_blobs.md)
explica a ordem, as hipóteses e as decisões condicionadas aos resultados.

## Próxima execução, quando retomarmos

Primeiro executar os testes sintéticos preparados, ainda não executados:

```powershell
& "C:\Python313\python.exe" -m unittest scripts.testes.test_medidas_blobs scripts.testes.test_blobs scripts.testes.test_inspecao_blobs scripts.testes.test_diagnostico_blobs scripts.testes.test_diagnosticar_round0
```

Depois, com os testes aprovados, analisar os registros já existentes:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\diagnosticar_round0.py" --origem ".\resultados\frame-to-frame\blobs\round0\inspecao__20260920T041252237886Z"
```

O comando não executa o detector. Confere a origem e gera uma nova pasta
`diagnostico__<execucao>/` dentro de `resultados/frame-to-frame/blobs/round0/`.
Abra `guia_revisao.md`, confira as tabelas e copie `modelo_revisao_humana.csv`
para `revisao_humana_preenchida.csv` antes de preencher; preserve o modelo
incluído nos hashes. Consulte as comparações originais. Centros dentro de
caixas são relações geométricas,
não novos acertos, correspondências exclusivas ou critérios de ranking.
O diagnóstico não gera novas imagens ou PDF; reutiliza as comparações e
mantém o PDF original. Ele não dispara testes de filtros nem adaptações de caixa.

O código de diagnóstico e seus testes estão preparados para execução posterior.
Valores das próximas configurações serão fixados após essa análise. As
instruções seguintes servem para reproduzir a inspeção original.

## Reproduzir a inspeção original

No PowerShell, na raiz do projeto, instale as dependências no Python que
executará a inspeção:

```powershell
& "C:\Python313\python.exe" -m pip install -r ".\algoritmos\classicos\requirements-blobs.txt" -r ".\analise\requirements.txt" -r ".\analise\requirements-relatorio.txt"
```

Depois execute o único comando da inspeção:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_inspecao.py"
```

Sem argumentos, o script usa [inspecao/round0.json](inspecao/round0.json).
`--plano` aceita outro arquivo de inspeção validado, sem escolher imagens
ou configurações automaticamente. Cada repetição cria novas pastas; não há
sobrescrita nem retomada automática de uma execução parcial.

O plano contém **6 imagens de desenvolvimento × 2 configurações = 12
avaliações**. O detector recebe somente a imagem e os parâmetros. As
anotações servem para avaliação e comparação visual. Os originais são preservados.

| Vídeo / quadro | Normal | Aglomerado | Pequeno | Motivo da inspeção |
|---|---:|---:|---:|---|
| 11 / 0 | 43 | 0 | 0 | Referência utilizada no primeiro teste da limiarização |
| 12 / 200 | 29 | 1 | 3 | Presença das três classes |
| 19 / 0 | 19 | 4 | 0 | Aglomerados e objetos próximos das bordas |
| 21 / 0 | 21 | 0 | 3 | Pequenos em outro vídeo |
| 23 / 0 | 4 | 0 | 0 | Poucos objetos |
| 36 / 1300 | 44 | 0 | 1 | Muitos objetos e presença de bordas |

Os quadros pertencem ao conjunto fixo de 178 imagens. A escolha usa a
composição das anotações, sem resultados do novo detector. O executor confere
esse vínculo, os caminhos e os hashes antes de iniciar. Nenhum quadro de
seleção ou avaliação final participa do round0.

## Parâmetros de sondagem

`b01` procura objetos claros; `b02`, escuros. Os demais valores são iguais:

| Parâmetro | Valor inicial | Justificativa |
|---|---|---|
| Limiares | 10 a 240, em passos de 10; máximo 250 exclusivo | Exploração ampla das intensidades uint8 |
| Repetição mínima | 2 | Exigir recorrência de candidatos na exploração |
| Distância mínima | 3 pixels | Sondar objetos próximos sem impor grande distância |
| Área interna | De 3 inclusive a 5.000 exclusive | Limites amplos para observar candidatos pequenos e grandes |
| Filtros de circularidade, inércia e convexidade | Desligados | Examinar primeiro a representação sem seleção de forma |
| Pequeno | Área estimada ≤ π × 4² ≈ 50,2655 px² | Hipótese geométrica equivalente a diâmetro ≤ 8 pixels |
| Aglomerado | Área estimada ≥ π × 12² ≈ 452,3893 px² | Hipótese geométrica equivalente a diâmetro ≥ 24 pixels |
| Normal | Área estimada entre os dois limites | Completar a regra inicial das três classes |

Esses valores **não estão calibrados**. Os limites de diâmetro são hipóteses
de sondagem, não uma definição biológica nem quantis medidos nas anotações.
O filtro interno usa área de contorno; o classificador usa área de círculo
estimado. Os limiares de área da limiarização não foram transferidos como
se fossem medidas equivalentes.

Todos os parâmetros efetivos do OpenCV, inclusive filtros desligados, ficam
registrados. A versão de referência é `opencv-python 4.13.0.92`; versões
realmente importadas são registradas na execução. O plano é determinístico:
seed 42 é metadado, sem sorteio nesta etapa. Para repetir, use o plano salvo.

## Saídas e interpretação

As saídas ficam em `resultados/frame-to-frame/blobs/round0/`. A pasta
`inspecao__<execucao>/` reúne plano, manifesto, código arquivado, resumos
e relatório PDF. As pastas `<configuracao>__<execucao>/` ficam ao lado dela
e contêm os resultados por quadro, com imagens comparativas, tabelas e caixas
no formato YOLO. O terminal informa o caminho da inspeção ao terminar.

As comparações mostram as anotações à esquerda e as detecções à direita.
O resumo apresenta o **F1 de indivíduos 0/2**, precisão, recall, cobertura de
normais e pequenos, erros de classificação e aglomerados separados. Há também
resultados por quadro. O total agrega contagens antes de calcular F1; não
transforma estas seis imagens em uma seleção de configurações.

| Informação da detecção | Como interpretar |
|---|---|
| Caixa | Aproximação pelo centro e diâmetro, recortada nos limites da imagem |
| `centro_blob_x_px`, `centro_blob_y_px` | Posição estimada do blob, diferente do centro geométrico da caixa recortada |
| `diametro_blob_px`, `area_estimada_blob_px2` | Estimativas anteriores ao recorte |
| `area_caixa_px2`, `alongamento_caixa` | Geometria do retângulo exportado; não a área ou forma real do objeto |
| `caixa_recortada_na_borda` | Informa se o retângulo foi limitado pela imagem |
| `area_pixels`, centroide da região, ocupação e intensidade | Ausentes; não houve recuperação da máscara segmentada |
| `limiar_utilizado` | Ausente porque o detector utiliza vários limiares |

Valores ausentes são `null` no JSON e campos vazios nas tabelas, não zeros.
Uma imagem sem objetos ou sem detecções conserva seus registros e cabeçalhos.
Índices de detecção não identificam indivíduos ao longo do tempo. Nesta
inspeção em JPEG, o tempo do quadro permanece ausente.

O PDF pode ser gerado novamente sem repetir o detector:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_inspecao.py" --somente-relatorio ".\resultados\frame-to-frame\blobs\round0\inspecao__<execucao>"
```

Substitua `<execucao>` pelo identificador da pasta produzida. Um novo relatório
preserva os anteriores. Falha na geração do PDF não transforma as métricas
concluídas em uma nova execução; o aviso informa o problema.

## O que revisar antes do round1

1. As caixas cobrem as cabeças anotadas ou representam apenas brilho/halo?
2. Objetos próximos recebem caixas distintas? Existem duplicações evidentes?
3. Pequenos e aglomerados aparecem nas saídas, mesmo quando classificados errado?
4. As perdas decorrem de posição/tamanho da caixa, rejeição do candidato ou
   troca entre indivíduo e aglomerado? Pareamento e imagens ajudam a investigar.
5. Os valores estimados, os recortes nas bordas e os arquivos estão coerentes?

Um F1 baixo aqui é um diagnóstico, não prova isolada de inviabilidade.
O resultado atual exige investigar também os candidatos excedentes, além
das caixas pequenas. O roteiro está no plano dos próximos testes. As
configurações das rodadas, a seleção e os vídeos ainda não estão preparados.

## Testes de código

Os testes usam dados sintéticos e pastas temporárias; não executam experimentos
com a base. Para executá-los:

```powershell
& "C:\Python313\python.exe" -m unittest scripts.testes.test_medidas_blobs scripts.testes.test_blobs scripts.testes.test_inspecao_blobs
```

Eles conferem geometria, tipos, fronteiras, preservação da entrada,
compatibilidade das medidas antigas, validação do plano e exportação.
Não substituem a inspeção das imagens reais do round0.

O ciclo posterior e suas limitações estão no
[plano do detector](../../analise/plano_blobs.md).
