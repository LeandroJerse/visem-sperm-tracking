# Guia de execução de blobs

O round0 foi executado em `inspecao__20260920T041252237886Z`: 12 avaliações
concluídas, com arquivos íntegros, mas localização insuficiente. O diagnóstico
dos registros também terminou: 12/12 casos e 36 testes sintéticos aprovados.
A [análise do round0](../../analise/diagnostico_round0_blobs.md) mostra caixas
pequenas apesar de conversão coerente, além de candidatos excedentes.
O formato e a exportação são compatíveis com o avaliador. **O round1 foi
concluído e analisado, assim como round2, round3 e round4.** A
[síntese de continuidade](../../analise/estado_pesquisa.md) registra as caixas
original/escala/margem e o orçamento aprovados.
O [plano completo dos próximos testes](../../analise/plano_diagnostico_blobs.md)
explica a ordem, as hipóteses e as decisões condicionadas aos resultados.

## Avaliação final concluída: comandos de reprodução

O batch `batch__20260921T034832637647Z` concluiu 29.550 avaliações e vinte
vídeos, com PDF e integridade conferidos. A [conclusão](../../analise/conclusao_blobs.md)
registra os resultados. Não é necessário repetir blobs para iniciar o
[round0 de watershed](../watershed/README.md).

O [plano final](../../analise/plano_videos_final_blobs.md) mantém **s052, s082,
s084, s103 e s051** nos vídeos completos **14, 24, 38 e 82**: 5.910 frames
por configuração, **29.550 avaliações e vinte MP4 comparativos**, tabelas e PDF.
Na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_videos.py" --etapa final
```

Saídas em `resultados/videos/blobs/final/batch__<execucao>/`, com as cópias
de procedência dentro de `origens/`. A execução cabe ao pesquisador; não é
necessário repetir rodadas ou seleção. Acrescente `--conferir` para conferir
somente arquivos, dependências e metadados, sem detecção ou criação de resultados.

## Reproduzir os vídeos de seleção concluídos

A seleção `batch__20260921T011058635016Z` concluiu **7.140 avaliações**.
Os 51.158 hashes de saídas, 134 de entradas/origens e o PDF de sete páginas
foram conferidos. Após a [análise](../../analise/analise_selecao_blobs.md), foram aprovadas
**s052, s082, s084, s103 e s051**, sem empate na quinta vaga. As limitações
de pequenos, aglomerados e classificação permanecem registradas.

O [plano dos vídeos](../../analise/plano_videos_blobs.md) foi executado:
**5.850 frames por configuração, 29.250 avaliações e 20 MP4 comparativos**
nos vídeos 13, 29, 52 e 54, com parâmetros e métricas preservados.
A [análise](../../analise/analise_videos_selecao_blobs.md) confirma a integridade
do batch `batch__20260921T022547636341Z`. s052 lidera com F1 0,668702.
O comando abaixo reproduz a etapa concluída; não é necessário executá-lo agora.

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_videos.py" --etapa selecao
```

As saídas ficam em `resultados/videos/blobs/selecao/batch__<execucao>/`:
uma pasta por configuração, com vídeos anotados, tabelas e PDF automático.
As 22 cópias de procedência ficam em `origens/`, separadas dos resultados atuais.
Acrescente `--conferir` para conferir arquivos e metadados sem executar
detecção. O alinhamento completo é conferido antes da primeira detecção.
Uma falha apenas no PDF permite usar `--somente-relatorio "<pasta do batch>"`.
A avaliação final está concluída; o comando no início deste guia permite reproduzi-la.

## Reproduzir a seleção concluída

O desenvolvimento terminou. O [plano de seleção](selecao/plano.json) compara
as 119 configurações distintas nos mesmos **60 frames dos vídeos 13, 29,
52 e 54**: 7.140 avaliações. Parâmetros, caixas, classes e critérios permanecem
congelados. Veja o [protocolo desta etapa](../../analise/plano_selecao_blobs.md).

Na raiz do projeto, execute:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_selecao.py"
```

O comando confere as entradas e gera comparações, tabelas, ranking e PDF
automaticamente em `resultados/frame-to-frame/blobs/selecao/`. Cada tentativa
cria novas pastas. Acrescente `--conferir` para apenas conferir o plano,
as origens, as imagens e as dependências, sem executar detecções.
**Não é necessário repetir as rodadas anteriores.**

Abra `ranking.csv`, coluna `f1_individuos`, e o PDF indicado em `relatorio.json`
dentro de `batch__<execucao>/`. O plano relaciona os IDs `s001`–`s119` aos IDs
das rodadas. As cinco configurações aprovadas estão registradas no início
deste guia; o comando acima reproduz a seleção histórica.

Se precisar gerar somente outro PDF, sem repetir a detecção:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_selecao.py" --somente-relatorio ".\resultados\frame-to-frame\blobs\selecao\batch__<execucao>"
```

Substitua `<execucao>` pelo nome da tentativa concluída. O executor das rodadas
continua disponível para reprodução do desenvolvimento, conforme as seções abaixo.

## Reproduzir o round5 concluído

As 2.492 avaliações foram conferidas, incluindo 17.532 hashes de saídas,
363 origens, quatro controles reproduzidos e PDF de quatro páginas.
O maior F1 passou de 0,567571 para 0,568779. A
[análise do round5](../../analise/analise_round5_blobs.md) e o
[documento completo de blobs](../../analise/desenvolvimento_blobs.html)
registram os resultados e os limites. A seleção foi concluída e está analisada
no início deste guia; os vídeos permanecem pendentes.

O [plano do round5](../../analise/plano_round5_blobs.md) contém **14 configurações
× 178 quadros = 2.492 avaliações**. São seis SBD, seis DoG e dois LoG,
incluindo quatro controles e dez novas configurações. Com ele, os cinco
planos somam 119 configurações distintas. O comando abaixo reproduz a rodada concluída.

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round5
```

Acrescente `--conferir` para validar entradas e dependências sem detectar
nem criar resultados. Não é necessário repetir rodadas anteriores.
O plano congelado é [round5.json](rodadas/round5.json); o gerador
`planejamento_round5.py` é interno, sem novo comando de execução.

SBD cruza área mínima 56/64/72 com margem 2/3. DoG cruza resposta
0,10/0,12/0,14 com margem 5/6. LoG mantém resposta 0,12 e margem 6,
comparando apenas o limite de aglomerado equivalente a diâmetro 24/28.
Essa última mudança pode afetar os acertos de indivíduos e aglomerados;
é uma hipótese a testar, mantendo as mesmas regras de avaliação.

As saídas ficam em `resultados/frame-to-frame/blobs/round5/`, com pasta
por tentativa, comparações, tabelas, ranking e PDF automático de quatro
páginas. A última página diferencia seis pares de margem e um par de
classificação. Seed 42, grade fixa, hashes e versões registram a reprodução.
O documento completo de blobs foi produzido após a análise do round5,
antes da preparação da seleção em outras imagens e dos vídeos.

## Reproduzir o round4 concluído

Round4 concluído: **3.204 avaliações**,22.535 hashes de saídas conferidos,
cinco controles reproduzidos e PDF válido. Maior F1 permanece0,567571;
a melhor configuração nova atingiu0,566181. Veja a
[análise do round4](../../analise/analise_round4_blobs.md).
O comando abaixo repete round4; a etapa atual é a execução dos vídeos de seleção.

O round3 concluiu 4.272 avaliações, com todos os 30.046 hashes de saídas
conferidos e os quatro controles reproduzidos. Melhor F1: **0,567571**.
DoG alcançou 0,544980, mas classificar e localizar pequenos continuam
limitados. Veja a [análise](../../analise/analise_round3_blobs.md).

O [plano do round4](../../analise/plano_round4_blobs.md) contém 18 configurações
nos mesmos 178 quadros: seis SimpleBlob, oito DoG e quatro LoG. Cinco são
repetições e 13 são novas, totalizando 109 distintas acumuladas.

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round4
```

São **3.204 avaliações**, com comparações, tabelas, ranking e PDF em
`resultados/frame-to-frame/blobs/round4/`. Acrescentar `--conferir` valida
entradas e dependências sem detectar nem criar resultados. Não é necessário
repetir rodadas anteriores. O plano congelado está em [round4.json](rodadas/round4.json).

SimpleBlob combina área48/64/80 e margem2/3, com distância6 fixa. DoG combina
resposta0,12/0,16/0,20/0,24 e margem6/8. LoG conserva resposta0,08/0,12 e
testa margem5/6, mantendo a investigação dos pequenos e de caixas grandes.
As margens diferentes seguem o diagnóstico por método.

O PDF conserva quatro páginas e mostra nove pares de margem na última.
O gerador `planejamento_round4.py` é interno; a execução continua pelo mesmo
script. As grades são fixas, com seed42 registrada e sem sorteio em execução.
As saídas anteriores são preservadas. A análise do round4 fundamenta o
plano do round5 descrito acima.

## Reproduzir o round3 concluído

O [desenho aprovado](../../analise/proposta_round3_blobs.md) está congelado em
[rodadas/round3.json](rodadas/round3.json). São **24 configurações × 178 quadros
= 4.272 avaliações**: 12 combinações de área, distância e margem no
SimpleBlobDetector e 12 de resposta e margem em LoG/DoG. Quatro controles
repetem configurações anteriores; as 20 novas levam o acumulado a 96 distintas.

Na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round3
```

O mesmo executor salva comparações, tabelas, ranking e PDF em
`resultados/frame-to-frame/blobs/round3/`, com novas pastas por tentativa.
Acrescente `--conferir` para apenas conferir plano, dependências e entradas.
Não é necessário reinstalar dependências nem repetir round1 e round2.

O plano inclui parâmetros completos, identidades das configurações anteriores,
fontes e hashes. A geração usa uma grade fixa e ordem explícita; seed 42 é
registrada, mas não há sorteio nem adaptação durante a execução. O gerador
interno `planejamento_round3.py` não é um novo comando de execução.

O PDF mantém os gráficos de F1, precisão/recall, cobertura e resultados por
vídeo. A quarta página compara 12 pares que diferem somente na margem da caixa.
Depois da execução, analisar também área, distância, resposta e suas interações,
sem escolher finalistas nesta rodada. A faixa DoG continua sem alcançar
diâmetro suficiente para prever aglomerados; essa limitação está documentada.

## Reproduzir o round2 concluído

O batch `batch__20260920T203403161690Z` concluiu as 5.696 avaliações, com
41.489 hashes íntegros e os quatro controles reproduzindo o round1.
Melhor F1: 0,556433. A [análise](../../analise/analise_round2_blobs.md)
e o [plano do round3](../../analise/proposta_round3_blobs.md) explicam a
continuidade. Os comandos
abaixo repetem o round2; não executam a próxima rodada.

O [plano e as justificativas](../../analise/plano_round2_blobs.md) mantêm
32 configurações: quatro referências repetidas, 12 refinamentos, oito CLAHE,
quatro LoG e quatro DoG. São 5.696 avaliações nos mesmos 178 quadros.
O round1 permanece como referência; não é necessário reiniciá-lo.

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round2 --conferir
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round2
```

O primeiro comando apenas confere as entradas. O segundo executa a rodada;
suas saídas ficam em `resultados/frame-to-frame/blobs/round2/`. Novos nomes
identificam método e pré-processamento, além da caixa e do hash. Todos guardam
`configuracao_backend.json`; SimpleBlobDetector conserva também o registro
OpenCV. LoG/DoG exportam sigma e a origem das medidas. CLAHE salva a imagem
processada, com tempo separado. Comparações continuam sobre o fundo original.

O PDF utiliza gráficos ordenados e mapas por vídeo, conservando F1 de
indivíduos, cobertura por classe e erros de classificação. Pode ser atualizado
para rodadas antigas sem repetir detecções. A referência adicional de
ambiente é `scikit-image==0.26.0` (Python 3.11 ou posterior), já instalada
no Python 3.13.3 dos experimentos.
Para outro ambiente, use a instalação de dependências descrita adiante.

## Reproduzir o round1 concluído

Batch completo: `batch__20260920T193937586038Z`, com 48 configurações e
8.544 avaliações. Os 60.056 hashes de saídas e o PDF foram conferidos.
Veja a [análise e proposta do round2](../../analise/analise_round1_blobs.md).
O comando abaixo repete o round1; não executa a próxima rodada.

No PowerShell, na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round1
```

O [plano congelado](rodadas/round1.json) contém **48 configurações distintas
× 178 quadros = 8.544 avaliações**. São 12 comparações controladas, mantendo
os detectores b01/b02 e variando somente a caixa, e 36 configurações
exploratórias. A [justificativa dos parâmetros](../../analise/plano_round1_blobs.md)
explica o espaço de busca. A seed 42 gerou a lista; executar o plano salvo
não faz novos sorteios nem altera parâmetros durante a rodada.

O executor confere dependências, os 178 pares de imagem/anotação e seus
hashes antes de começar. Para repetir apenas essa conferência:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round1 --conferir
```

Essa opção não detecta objetos nem cria resultados. Em 20/09/2026, a
conferência passou no Python indicado. As dependências necessárias já
estavam instaladas; a instalação descrita adiante serve para outro ambiente.

### Onde ficam as saídas

```text
resultados/frame-to-frame/blobs/round1/
├── batch__<execucao>/
│   ├── plano.json, codigo.zip, execucao.json
│   ├── resumo_configuracoes.csv, resumo_por_video.csv, resumo_por_quadro.csv
│   ├── ranking.csv, relatorio.json
│   └── relatorios/<geracao>/relatorio.pdf
└── r1c01__blobs-claro-original__cfg-<hash>__<execucao>/
    ├── configuracao.json, configuracao_opencv.json, execucao.json
    ├── avaliacao.json, resumo_por_quadro.csv
    └── quadros/<video>_frame_<quadro>/
        ├── comparacao.png, predicoes.txt, avaliacao.json
        └── anotacoes.csv, deteccoes.csv, pares.csv, pendentes.csv
```

Cada configuração tem sua pasta irmã do batch. O nome informa ID, polaridade,
modo/tamanho da caixa e hash dos parâmetros completos. `configuracao.json`
guarda todos os valores. `<execucao>` é a data/hora UTC da tentativa.

**Onde ver o F1:** `ranking.csv`, coluna `f1_individuos`. Os resumos e o PDF
mostram também aglomerados, cobertura das três classes, classificação nos
pares válidos e desempenho por vídeo. F1 soma TP/FP/FN antes do cálculo;
trocas entre 0 e 2 são registradas separadamente. Empates exatos mantêm a
mesma posição. O ranking desta rodada orienta desenvolvimento; não escolhe
as cinco finalistas.

Caixas originais e adaptadas ficam registradas. A adaptação conserva centro,
diâmetro, área circular estimada, classes e índices dos candidatos. A margem
não aumenta a área usada para classificar o objeto. Tempos do detector,
adaptação e conjunto são separados; não incluem gravação, avaliação ou PDF.

Cada nova tentativa cria pastas novas. Resultados completos são registrados
progressivamente e uma interrupção tratável marca a tentativa como falha,
preservando o que já foi salvo. **Não há retomada automática:** repetir o
comando inicia outra tentativa. Em queda abrupta de energia, o registro pode
permanecer `em_andamento`; não deve ser interpretado como rodada concluída.

### Acesso negado durante o salvamento

A primeira tentativa, `batch__20260920T192425152218Z`, parou na configuração
12: o Windows negou a substituição de `execucao.json.tmp` por `execucao.json`.
Foram salvas 11 configurações completas e 87 quadros da seguinte. Os 13.761
hashes das configurações completas foram conferidos sem divergências.
Não houve conclusão nem PDF dessa tentativa.

O salvamento agora repete a substituição em caso de erros Windows 5, 32 e 33,
com espera crescente e limitada a cerca de nove segundos no total. Enquanto
a troca não acontece, o arquivo anterior é preservado. Essa repetição não
executa novamente o detector nem acrescenta linhas duplicadas às tabelas.
Se o bloqueio persistir, a execução continua falhando explicitamente; não há
garantia de resolver uma restrição permanente de acesso.

**O comando permanece o mesmo e não exige elevação para administrador.**
Não é necessário apagar a pasta round1: a próxima tentativa usa outro
identificador e preserva os registros da interrupção. O processo que impediu
a gravação não foi identificado pelo erro; não atribuir a causa a um programa
específico sem confirmação. A limiarização e o round0 mantêm seus executores.

A correção passou em 7 testes específicos de arquivos e 26 de executor e
relatório, incluindo bloqueios simulados sem repetir detecções nem linhas.
São testes técnicos; nenhuma rodada foi executada para verificar essa mudança.

Se somente o PDF falhar, as métricas concluídas permanecem válidas. Para
gerá-lo novamente, substitua `<execucao>` pelo nome informado ao terminar:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --somente-relatorio ".\resultados\frame-to-frame\blobs\round1\batch__<execucao>"
```

Cada geração preserva PDFs anteriores. `relatorio.json` aponta para o último.
Round1 a round5 estão concluídos e podem ser reproduzidos.

## Reproduzir o diagnóstico concluído

O resultado está em `diagnostico__20260920T175946938558Z`, dentro do round0.
Para reproduzir, primeiro executar os testes sintéticos do diagnóstico:

```powershell
& "C:\Python313\python.exe" -m unittest scripts.testes.test_diagnostico_blobs scripts.testes.test_diagnosticar_round0
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

Os valores do round1 estão no plano congelado. As instruções seguintes
servem para reproduzir a inspeção original, que permanece preservada.

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

## O que revisar nas comparações

1. As caixas cobrem as cabeças anotadas ou representam apenas brilho/halo?
2. Objetos próximos recebem caixas distintas? Existem duplicações evidentes?
3. Pequenos e aglomerados aparecem nas saídas, mesmo quando classificados errado?
4. As perdas decorrem de posição/tamanho da caixa, rejeição do candidato ou
   troca entre indivíduo e aglomerado? Pareamento e imagens ajudam a investigar.
5. Os valores estimados, os recortes nas bordas e os arquivos estão coerentes?

Um F1 baixo aqui é um diagnóstico, não prova isolada de inviabilidade.
O resultado atual exige investigar também os candidatos excedentes, além
das caixas pequenas. O roteiro está no plano dos próximos testes. As
configurações dos rounds investigaram essas hipóteses. Round5 foi concluído;
a seleção foi concluída e as cinco finalistas foram aprovadas.
Os vídeos completos de seleção foram concluídos e conferidos.

## Testes de código

A preparação final passou em **58 testes**: 14 do plano final, 22 do executor
e 22 do relatório. A conferência real com `--etapa final --conferir` passou
sem criar resultados, e o PDF final sintético de quatro páginas foi revisado.

```powershell
& "C:\Python313\python.exe" -m unittest scripts.testes.test_planejamento_videos_final_blobs scripts.testes.test_videos_blobs scripts.testes.test_relatorio_videos_blobs
```

A reorganização das origens passou em **46 testes**: 15 do executor,
15 do relatório e 16 da migração. A nova pasta `origens/` é gravada nas
execuções futuras e também foi aplicada ao batch concluído, preservando
métricas, vídeos e PDF. O relatório continua reconhecendo batches antigos.

```powershell
& "C:\Python313\python.exe" -m unittest scripts.testes.test_videos_blobs scripts.testes.test_relatorio_videos_blobs scripts.testes.test_organizacao_blobs
```

A preparação dos vídeos passou em **96 testes**: 19 do plano, 15 do executor,
13 do relatório e 49 de regressão dos utilitários de vídeo compartilhados.
Os MP4s de teste são sintéticos. O plano real, origens, anotações e metadados
passaram em `--conferir`, sem percorrer os vídeos nem criar resultados.
O PDF sintético de quatro páginas foi renderizado e revisado.

```powershell
& "C:\Python313\python.exe" -m unittest scripts.testes.test_planejamento_videos_blobs scripts.testes.test_videos_blobs scripts.testes.test_relatorio_videos_blobs scripts.testes.test_videos_limiarizacao
```

Os testes usam dados sintéticos e pastas temporárias; não executam experimentos
com a base. Para executá-los:

```powershell
& "C:\Python313\python.exe" -m unittest scripts.testes.test_medidas_blobs scripts.testes.test_blobs scripts.testes.test_inspecao_blobs
& "C:\Python313\python.exe" -m unittest scripts.testes.test_caixas_blobs scripts.testes.test_planejamento_blobs scripts.testes.test_executar_rodada_blobs scripts.testes.test_relatorio_rodada_blobs
& "C:\Python313\python.exe" -m unittest scripts.testes.test_planejamento_round5_blobs scripts.testes.test_executar_round5_blobs
& "C:\Python313\python.exe" -m unittest scripts.testes.test_planejamento_selecao_blobs scripts.testes.test_executar_selecao_blobs scripts.testes.test_relatorio_selecao_blobs
```

Eles conferem geometria, tipos, fronteiras, preservação da entrada,
compatibilidade das medidas antigas, validação do plano e exportação.
Não substituem a inspeção das imagens reais do round0.

Na preparação do round1 passaram 66 testes novos e 113 de regressão
(incluindo diagnóstico e avaliador). O PDF sintético com 48 configurações
teve suas oito páginas renderizadas e conferidas visualmente. Esses testes
não medem a eficácia das configurações na base.

O ciclo posterior e suas limitações estão no
[plano do detector](../../analise/plano_blobs.md).
