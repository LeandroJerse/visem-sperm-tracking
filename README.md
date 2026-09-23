# Detecção de espermatozoides em imagens e vídeos

Projeto de TCC para comparar métodos de detecção de espermatozoides em imagens
de microscopia. Os objetos encontrados são comparados com as anotações da base
VISEM-Tracking, permitindo medir acertos, falsas detecções, perdas e erros de
classificação.

A **limiarização manual/Otsu** e os detectores de **blobs** concluíram o ciclo
de desenvolvimento, seleção e avaliação final. Veja a [conclusão de blobs](analise/conclusao_blobs.md)
e o [documento de suas cinco rodadas](analise/desenvolvimento_blobs.html).
**Watershed concluiu as cinco rodadas**, com maior F1 de localização de
**0,482362** no desenvolvimento. A [análise do round5](analise/analise_round5_watershed.md)
registra a conferência e as limitações. A [seleção foi concluída e conferida](analise/analise_selecao_watershed.md):
**114 configurações distintas × 60 imagens = 6.840 avaliações**, com ranking
e PDF. A líder s063 teve F1 **0,342956**. Foram aprovadas **s063, s064,
s061, s062 e s098** para os vídeos completos de seleção. O
[plano de vídeos](analise/plano_videos_watershed.md) está preparado para execução.
O [guia de watershed](scripts/watershed/README.md)
traz os comandos e as saídas; o [plano técnico](analise/plano_watershed.md) explica caixas, sementes
e as duas políticas de aglomerados. Os experimentos começam em imagens fixas
e avançam para vídeos completos. Métodos híbridos com k-NN são uma etapa posterior.
A comparação com detectores modernos, como YOLO, também faz parte do planejamento.

As saídas incluem caixas, classes, medidas e tempos dos quadros. Na limiarização,
as medidas vêm dos pixels segmentados; em blobs, centro, diâmetro e área são
estimativas, registradas em campos próprios.
Esses dados poderão apoiar estudos de movimento. A implementação atual faz
detecção quadro a quadro; ainda não associa o mesmo indivíduo entre quadros
nem calcula trajetórias ou velocidades.

## Organização do projeto

| Pasta | Conteúdo |
|---|---|
| `algoritmos/classicos/` | Detectores, estruturas de dados e classificação por área |
| `scripts/blobs/` | Inspeção, diagnóstico, rodadas, seleção e vídeos de blobs |
| `scripts/watershed/` | Inspeção, cinco rodadas, seleção em imagens e vídeos de seleção |
| `scripts/limiarizacao/` | Execução individual, rodadas, seleção e vídeos |
| `scripts/limiarizacao/rodadas/` | Planos de parâmetros de `round1` a `round5` |
| `scripts/limiarizacao/selecao/` | Plano de comparação das configurações em imagens |
| `scripts/limiarizacao/videos/` | Planos dos vídeos de seleção e avaliação final |
| `scripts/avaliacao/` | Avaliação de imagem individual e geração de relatórios |
| `analise/` | Métricas, relatórios, protocolo e análises das rodadas |
| `bases_de_dados/` | Vídeos, imagens e anotações originais, mantidos localmente |
| `resultados/` | Mídias, tabelas, configurações e registros das execuções |

## Próxima execução: watershed nos vídeos de seleção

Na raiz do projeto, execute:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_videos.py" --etapa selecao
```

As cinco configurações aprovadas serão aplicadas aos vídeos completos **13,
29, 52 e 54**: **29.250 avaliações e 20 vídeos comparativos**, com anotações
à esquerda e detecções à direita. O PDF de quatro páginas será automático.
As saídas ficam em `resultados/videos/watershed/selecao/batch__<UTC>/`.
Use `--conferir` para verificar apenas arquivos e metadados. Após a execução,
revisaremos os resultados antes de preparar os vídeos finais 14, 24, 38 e 82.
Consulte o [plano e organização das saídas](analise/plano_videos_watershed.md).

## Reproduzir a seleção de watershed em imagens

A seleção já foi concluída; não é necessário repeti-la. Para reprodução,
na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_selecao.py"
```

O plano reúne todas as configurações distintas, sem novos ajustes, nos
quadros 0, 100, …, 1400 dos vídeos 13, 29, 52 e 54. As saídas ficam em
`resultados/frame-to-frame/watershed/selecao/batch__<UTC>/`, com pastas por
configuração/quadro, tabelas e PDF de oito páginas. Acrescente `--conferir`
para verificar somente as entradas. A [análise](analise/analise_selecao_watershed.md)
explica o ranking e as limitações. As cinco candidatas já foram aprovadas;
o comando anterior executa a etapa seguinte, nos vídeos completos de seleção.
O [guia de watershed](scripts/watershed/README.md) explica reprodução e recuperação do PDF.

## Situação de blobs

O [diagnóstico concluído](analise/diagnostico_round0_blobs.md) identificou
caixas subdimensionadas e candidatos excedentes; a conversão das coordenadas
está coerente. Os 12 casos e os 36 testes do diagnóstico foram concluídos.
O [guia de blobs](scripts/blobs/README.md) reúne os comandos e explica as saídas.
**Seleção concluída: 119 configurações comparadas nos 60 frames.**
As 7.140 avaliações e seus arquivos foram conferidos. A
[análise da seleção](analise/analise_selecao_blobs.md) fundamentou a aprovação de
**s052, s082, s084, s103 e s051** para os vídeos completos.
O maior F1 foi 0,669617; pequenos, aglomerados e classificação ainda têm limitações.
O [plano dos vídeos](analise/plano_videos_blobs.md) mantém parâmetros e métricas
das cinco aprovadas e processa integralmente os vídeos 13, 29, 52 e 54:
**29.250 avaliações e 20 MP4 comparativos**, com tabelas, ranking e PDF.
A execução `batch__20260921T022547636341Z` foi concluída e conferida:
**s052 liderou com F1 0,668702**. Veja a [análise dos vídeos](analise/analise_videos_selecao_blobs.md).
A [avaliação final está preparada](analise/plano_videos_final_blobs.md),
mantendo as cinco configurações nos vídeos **14, 24, 38 e 82**.
No PowerShell, na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_videos.py" --etapa final
```

O comando produz **29.550 avaliações e vinte MP4 comparativos**, com tabelas
e PDF, em `resultados/videos/blobs/final/`. As fontes ficam em `origens/`.
A execução será feita pelo pesquisador. Acrescente `--conferir`
para verificar arquivos e metadados sem executar detecção. Não é necessário
repetir desenvolvimento ou seleção em imagens/vídeos;
o [guia de blobs](scripts/blobs/README.md) conserva os comandos de reprodução.
Os registros abaixo resumem as rodadas já concluídas.

O [plano do round1](scripts/blobs/rodadas/round1.json) tem **48 configurações
distintas × 178 frames = 8.544 avaliações**: 12 comparações controladas e
36 exploratórias, com seed 42. O executor gera comparações, tabelas e PDF em
`resultados/frame-to-frame/blobs/round1/`, criando uma pasta nova por tentativa.
A primeira tentativa parou por acesso negado ao salvar um arquivo de controle;
o [guia](scripts/blobs/README.md#acesso-negado-durante-o-salvamento) registra a
correção e a repetição. Na preparação passaram a conferência das entradas e
179 testes técnicos; isso verifica a infraestrutura, não o desempenho na base.
A repetição `batch__20260920T193937586038Z` concluiu as 8.544 avaliações e
gerou o PDF. A [análise do round1](analise/analise_round1_blobs.md) registra
melhor F1 de indivíduos de 0,551828, baixa cobertura de pequenos e a proposta
inicial do round2. A [decisão aprovada e seus motivos](analise/plano_round2_blobs.md)
estão registrados separadamente: **32 configurações × 178 quadros = 5.696
avaliações**, com quatro repetições, 12 refinamentos, oito CLAHE e oito LoG/DoG.
As saídas seguem em `resultados/frame-to-frame/blobs/round2/`. O round1 não
foi reiniciado; para reproduzi-lo, basta usar `--rodada round1`.

O round3 terminou íntegro: **4.272 avaliações**, quatro controles reproduzidos
e melhor F1 de indivíduos **0,567571**, ante 0,556433 no round2. DoG chegou
a 0,544980; localização de pequenos e classificação ainda têm limitações.
A [análise estatística e geométrica](analise/analise_round3_blobs.md) fundamenta o
[plano congelado do round4](scripts/blobs/rodadas/round4.json): **18 configurações
× 178 quadros = 3.204 avaliações**, sendo seis SimpleBlob, oito DoG e quatro LoG.
Cinco são referências repetidas e 13 são novas. Os resultados do round4
ficam em `resultados/frame-to-frame/blobs/round4/`. Para reproduzir rodadas
anteriores, use `--rodada round1` até `round4` no mesmo executor.

O round4 concluiu as 3.204 avaliações, com controles reproduzidos e arquivos
íntegros. **O melhor F1 permaneceu 0,567571**; a melhor configuração nova
chegou a 0,566181, com menos FP e também menos acertos. A
[análise do round4](analise/analise_round4_blobs.md) fundamenta o
[plano do round5](scripts/blobs/rodadas/round5.json): seis SBD, seis DoG e
dois LoG, sendo quatro controles e dez novas configurações. São **2.492
avaliações concluídas** e 119 configurações distintas no conjunto dos planos.
Para repetir o round5, use `executar_rodada.py --rodada round5`; suas saídas
ficam em `resultados/frame-to-frame/blobs/round5/`.
No LoG, um par muda somente o limite de aglomerado, equivalente a diâmetro
24→28; os outros testes refinam área, resposta e margem.
O round5 terminou íntegro, com controles reproduzidos. A melhor nova configuração,
r5c06, elevou F1 de 0,567571 para 0,568779, com 81 FP a menos e 26 TP a menos.
O documento completo está disponível. A seleção em outras imagens foi
concluída e analisada. O comando no início deste guia executa a próxima etapa:
os vídeos finais de blobs, preparados para execução. Os vídeos completos
de seleção já foram concluídos e conferidos.

A [síntese de continuidade](analise/estado_pesquisa.md) reúne decisões,
resultados e pendências. A [justificativa do round1](analise/plano_round1_blobs.md)
explica os valores e as hipóteses que orientaram sua preparação.
Foram aprovadas caixas originais, com escala ou margem, e até cinco rodadas
de 48/32/24/18/14 configurações, com teto de 122 distintas. As cinco rodadas
concluídas produziram 119 distintas dentro desse orçamento.
As seções numeradas abaixo reproduzem o ciclo já concluído da limiarização.

## 1. Preparar o ambiente

Os comandos abaixo usam **PowerShell no Windows**, a partir da raiz do projeto,
onde está este README. Para reproduzir também LoG/DoG, é necessário Python
**3.11 ou posterior**, exigido pelo scikit-image 0.26.0; os experimentos
registrados utilizaram Python 3.13.3.

Crie um ambiente virtual e instale as dependências:

```powershell
python -m venv .venv
$PythonTcc = (Resolve-Path ".\.venv\Scripts\python.exe").Path
& $PythonTcc -m pip install -r ".\algoritmos\classicos\requirements.txt" -r ".\analise\requirements.txt" -r ".\analise\requirements-relatorio.txt"
```

Se `python` não estiver disponível no terminal, substitua-o pelo caminho da
instalação, por exemplo `& "C:\Python313\python.exe" -m venv .venv`.
Não é necessário ativar o ambiente: os comandos usam diretamente seu executável.
Ao abrir outro terminal, entre novamente na raiz e redefina `$PythonTcc`.

Dependências: NumPy e OpenCV para detecção, SciPy para correspondência entre
caixas, Matplotlib e ReportLab para os PDFs. Os arquivos de requisitos usam
faixas de versões. Para reproduzir o ambiente de uma execução anterior,
consulte as versões registradas em seu `execucao.json`; instalar as faixas
atuais não garante resultados numericamente idênticos.

## 2. Disponibilizar dados e registros de reprodução

### Base de dados

A execução atual utiliza o conjunto anotado VISEM-Tracking. A estrutura
esperada para cada vídeo é:

```text
bases_de_dados/visem_tracking/dataset/Train/<video_id>/
├── <video_id>.mp4
├── images/<video_id>_frame_<quadro>.jpg
└── labels/<video_id>_frame_<quadro>.txt
```

Os dados não acompanham o repositório Git. Disponibilize uma cópia da base
nesses caminhos, preservando nomes e conteúdo. Os planos conferem os hashes
dos arquivos; imagens reconvertidas ou anotações alteradas não substituem
as fontes registradas. O inventário está em
[bases de dados](bases_de_dados/LEIA_PRIMEIRO.md).

Cada linha de `labels/` segue o formato:

```text
class_id center_x center_y width height
```

São **caixas delimitadoras**, com centro, largura e altura normalizados pelo
tamanho da imagem. As três classes originais são:

| Classe | Significado |
|---|---|
| 0 | Normal |
| 1 | Aglomerado (`cluster`) |
| 2 | Pequeno ou cabeça pequena (`small_or_pinhead`) |

Use `labels/`, não `labels_ftid/`: esta última contém um campo adicional de
identidade usado em rastreamento. Arquivo de anotação vazio significa zero
objetos; arquivo ausente é tratado como erro, salvo as exclusões já registradas
nos planos de desenvolvimento.

### Registros históricos exigidos pelos planos

**A reprodução completa requer código, dados e os registros históricos de
origem. Um clone do Git com a base, mas sem esses registros, não executa todas
as etapas.** A pasta `resultados/` também fica fora do Git.

Os planos de seleção e vídeos fixam caminhos e hashes de execuções anteriores.
Restaure os arquivos listados abaixo a partir do acervo do experimento,
mantendo os caminhos relativos à raiz. As novas execuções terão outras pastas
e não substituirão automaticamente essas referências.

| Etapa que será executada | Registros necessários |
|---|---|
| Rodadas 1–5 | Planos versionados e dados originais; não exigem resultados anteriores |
| Seleção em imagens | `rodada.json`, `execucao.json`, `resumo_configuracoes.csv` e `resumo_por_video.csv` de cada um dos cinco batches abaixo; também usa `analise/rodadas/desenvolvimento_resumo.json` |
| Reavaliação por indivíduos | Batch completo de seleção indicado por `--batch`, incluindo as tabelas de caixas e as pastas de configuração referenciadas |
| Vídeos de seleção | `execucao.json`, `ranking.csv`, `resumo_configuracoes.csv` e `resumo_por_video.csv` da reavaliação histórica abaixo |
| Vídeos finais | Os quatro arquivos da reavaliação histórica e `execucao.json`, `plano.json`, `ranking.csv`, `resumo_configuracoes.csv`, `resumo_por_video.csv` do batch histórico de vídeos de seleção |

Os cinco batches de desenvolvimento ficam sob
`resultados/frame-to-frame/limiarizacao/`:

```text
round1/batch__20260919T192640642218Z/
round2/batch__20260919T203029199281Z/
round3/batch__20260919T205704135470Z/
round4/batch__20260919T215117276355Z/
round5/batch__20260920T010415641826Z/
```

As demais fontes congeladas são:

```text
resultados/frame-to-frame/limiarizacao/selecao/batch__20260920T012713968145Z/reavaliacoes_individuos/20260920T021112218814Z/
resultados/videos/limiarizacao/selecao/batch__20260920T023832151694Z/
```

Os caminhos e hashes completos estão no [plano de seleção em imagens](scripts/limiarizacao/selecao/plano.json),
no [plano de vídeos de seleção](scripts/limiarizacao/videos/plano_selecao.json)
e no [plano final](scripts/limiarizacao/videos/plano_final.json).
Reexecutar as rodadas não recria os manifestos históricos com os mesmos hashes,
pois eles incluem horários e registros da execução. Não renomeie novas saídas
nem altere hashes para fazê-las passar como fontes anteriores.

## 3. Conhecer a sequência experimental

```text
Rodadas em imagens: round1 → round2 → round3 → round4 → round5
  → Comparação das 122 configurações distintas em outras imagens
  → Reavaliação das mesmas caixas pelo critério de indivíduos
  → Cinco configurações nos vídeos completos de seleção
  → Mesmas cinco configurações nos vídeos completos de avaliação final
```

| Partição | Vídeos | Uso |
|---|---|---|
| Desenvolvimento | 11, 12, 15, 19, 21, 22, 23, 30, 35, 36, 47, 60 | Ajuste de parâmetros nas cinco rodadas |
| Seleção | 13, 29, 52, 54 | Comparação em imagens e teste das cinco configurações em vídeos completos |
| Avaliação final | 14, 24, 38, 82 | Avaliação das cinco escolhas com parâmetros congelados |

Nas imagens, são usados os quadros `0, 100, ..., 1400`. No desenvolvimento,
faltam as anotações dos quadros 900 e 1100 do vídeo 23: as duas exclusões estão
registradas e restam **178 quadros**, iguais para todas as configurações.
A seleção utiliza **60 quadros**, sem exclusões.

Os planos prontos reproduzem as escolhas do experimento. As rodadas posteriores
foram definidas a partir da análise das anteriores; executar a sequência não
realiza uma nova busca automática. O [protocolo](analise/protocolo_rodadas.md)
e as [análises das rodadas](analise/rodadas/) registram os critérios e os motivos.

## 4. Executar as cinco rodadas em imagens

Execute os comandos abaixo em ordem, aguardando cada rodada terminar antes
da seguinte. Cada comando inclui detecção, avaliação, imagens comparativas,
tabelas e relatório PDF.

```powershell
& $PythonTcc ".\scripts\limiarizacao\executar_rodada.py" --rodada round1
& $PythonTcc ".\scripts\limiarizacao\executar_rodada.py" --rodada round2
& $PythonTcc ".\scripts\limiarizacao\executar_rodada.py" --rodada round3
& $PythonTcc ".\scripts\limiarizacao\executar_rodada.py" --rodada round4
& $PythonTcc ".\scripts\limiarizacao\executar_rodada.py" --rodada round5
```

| Rodada | Configurações | Quadros por configuração | Avaliações |
|---|---:|---:|---:|
| round1 | 48 | 178 | 8.544 |
| round2 | 32 | 178 | 5.696 |
| round3 | 24 | 178 | 4.272 |
| round4 | 18 | 178 | 3.204 |
| round5 | 14 | 178 | 2.492 |

Os resultados ficam em `resultados/frame-to-frame/limiarizacao/round<N>/`.
A subpasta `batch__<execucao>/` contém os resumos; as pastas das configurações
ficam ao lado dela, dentro da rodada. Consulte `pasta` no resumo para localizar
as imagens e tabelas de cada configuração.

A primeira rodada usa amostragem com seed 42; as seguintes são listas fixas.
Para reproduzir o experimento, use os JSONs salvos. `preparar_rodada.py` gera
uma nova exploração inicial e **não precisa ser executado** neste roteiro;
ele não reconstrói as decisões das rodadas 2–5.

## 5. Comparar as configurações nas imagens de seleção

```powershell
& $PythonTcc ".\scripts\limiarizacao\executar_selecao.py"
```

São **122 configurações distintas × 60 quadros = 7.320 avaliações**.
Repetições equivalentes das cinco rodadas são representadas uma única vez.
Os IDs `s001` a `s122` identificam as configurações; não são posições no ranking.

As saídas ficam em `resultados/frame-to-frame/limiarizacao/selecao/`, com
um novo `batch__<execucao>/` e as pastas das configurações ao lado.
Guarde o caminho do batch informado ao terminar: ele será usado na próxima etapa.
A verificação de origem continua utilizando os batches históricos da seção 2.

## 6. Reavaliar as caixas pelo critério de indivíduos

A comparação original das rodadas e da seleção usa macro-F1 das três classes.
Para reproduzir a avaliação atual, reavalie as caixas já salvas pelo critério
de indivíduos, sem executar novamente o detector.

Informe a **pasta do batch da etapa 5**, não o arquivo CSV nem a pasta de uma
configuração. O comando abaixo solicita esse caminho no terminal:

```powershell
$BatchSelecao = Read-Host "Caminho da pasta batch__... gerada na seleção em imagens"
& $PythonTcc ".\scripts\limiarizacao\reavaliar_selecao.py" --batch $BatchSelecao
```

O resultado será salvo em
`<batch>/reavaliacoes_individuos/<execucao>/`, com `ranking.csv`, resumos,
diagnósticos e PDF. **Não omita `--batch` ao reavaliar uma nova execução**:
sem ele, o script usa o batch histórico `batch__20260920T012713968145Z`.

O critério de indivíduos foi adotado depois da primeira seleção; por isso,
as duas avaliações permanecem separadas. As cinco configurações fixadas para
os vídeos são **s068, s067, s090, s099 e s101**. Uma repetição do ranking não
altera automaticamente essa composição.

## 7. Executar os vídeos completos de seleção

```powershell
& $PythonTcc ".\scripts\limiarizacao\executar_videos.py" --etapa selecao
```

Aplica as cinco configurações aos vídeos **13, 29, 52 e 54**:
**5.850 quadros por configuração**, **29.250 avaliações** e **20 vídeos
comparativos**, além das tabelas e do PDF.

Saída: `resultados/videos/limiarizacao/selecao/batch__<execucao>/`.
O plano preserva os parâmetros e verifica os registros da reavaliação histórica,
mesmo quando a etapa 6 tiver produzido uma nova reavaliação.

## 8. Executar a avaliação final em vídeos

```powershell
& $PythonTcc ".\scripts\limiarizacao\executar_videos.py" --etapa final
```

Aplica as mesmas cinco configurações aos vídeos **14, 24, 38 e 82**:
**5.910 quadros por configuração**, **29.550 avaliações** e **20 vídeos
comparativos**, além das tabelas e do PDF.

Saída: `resultados/videos/limiarizacao/final/batch__<execucao>/`.
O plano exige também os registros do batch histórico de vídeos de seleção.
**Sem `--etapa final`, o executor usa seleção.**

Os vídeos são processados integralmente, na resolução original. Antes da
detecção, o executor confere arquivos e alinhamento temporal em cinco
referências de cada vídeo; depois compara hashes dos pixels para assegurar
que todas as configurações recebam os mesmos quadros. Divergências interrompem
a execução. Cada MP4 gerado é reaberto para conferir dimensões, FPS e quantidade
de quadros.

Os resultados finais descrevem as escolhas congeladas. Não são usados para
novos ajustes nesse conjunto. A separação atual dos vídeos não elimina sua
exposição em experimentos anteriores; esse histórico deve acompanhar a
interpretação dos resultados.

## Como interpretar os resultados

No critério atual, uma correspondência exige **IoU ≥ 0,50**, entre objetos do
mesmo grupo, com associação um a um. O pareamento maximiza primeiro o número
de correspondências válidas e depois a soma das IoUs.

TP representa acertos; FP, falsas detecções; FN, objetos anotados que não
receberam uma detecção correspondente.

- **Indivíduos:** classes 0 e 2 juntas. Trocar normal por pequeno, ou o inverso,
  conta como acerto de detecção e erro de classificação separado.
- **Aglomerados:** classe 1, avaliada separadamente. Uma troca entre indivíduo
  e aglomerado continua sendo erro de detecção nos respectivos grupos.
- **F1:** `2 × TP / (2 × TP + FP + FN)`, calculado depois de somar as contagens.
  Não é a média dos F1 de quadros ou vídeos.
- **Sem casos:** F1 indefinido quando TP, FP e FN são todos zero. Se houver
  falsos positivos ou perdas, mas nenhum acerto, o F1 é zero.

| Arquivo | O que consultar |
|---|---|
| `execucao.json` | Situação, fontes, parâmetros de execução, versões e integridade |
| `resumo_configuracoes.csv` | Resultado agregado de cada configuração |
| `resumo_por_video.csv` | Diferenças de desempenho entre os vídeos |
| `ranking.csv` | F1 de indivíduos e empates, na reavaliação e nos batches de vídeo |
| `deteccoes.csv` | Caixas, classes, centroides, áreas e medidas dos objetos |
| `por_quadro.csv` | Contagens e métricas de cada quadro, inclusive sem detecções |
| `pares.csv` e `pendentes.csv` | Correspondências e objetos sem par; verificar o grupo de avaliação nas saídas históricas |
| `midia/` | Imagens ou vídeos: anotações à esquerda, detecções à direita |
| `relatorios/<execucao>/relatorio.pdf` | Gráficos e estatísticas descritivas |

Nas rodadas e na seleção original, consulte `macro_f1`. Na reavaliação e nos
vídeos, consulte `f1_individuos`, a cobertura das classes 0/2 e os erros de
classificação. Os dois critérios não são intercambiáveis. As contagens nos
vídeos representam ocorrências por quadro, não indivíduos únicos ao longo do tempo.

Cada repetição cria uma pasta nova identificada por data e hora UTC. Em caso
de falha, os arquivos parciais são preservados; **não há retomada automática**.
Considere o processamento concluído apenas com `situacao: "concluida"` no
manifesto. O PDF tem situação própria e pode falhar sem invalidar as métricas.
Pare diante de erros antes de avançar para a próxima etapa.

Os planos preservam configurações, ordem, fontes e seed. Horários, tempos de
processamento e bytes de PDFs ou vídeos exportados podem variar entre execuções.
Os manifestos e `codigo.zip` permitem identificar o código e o ambiente usados.

## Comandos complementares

### Inspecionar uma única imagem — round0

Esta inspeção é opcional e não integra as cinco rodadas. Pode ser feita antes
do batch para visualizar a saída do detector. Confira os parâmetros do JSON
de inspeção; os batches usam seus próprios planos e não dependem desse arquivo.

```powershell
& $PythonTcc ".\scripts\limiarizacao\inspecionar_imagem.py" --imagem ".\bases_de_dados\visem_tracking\dataset\Train\11\images\11_frame_0.jpg" --anotacao ".\bases_de_dados\visem_tracking\dataset\Train\11\labels\11_frame_0.txt" --config ".\scripts\configuracoes\limiarizacao.modelo.json"
```

Para calcular as métricas históricas dessa inspeção já salva:

```powershell
$Inspecao = Read-Host "Caminho da pasta de configuração gerada em round0"
& $PythonTcc ".\scripts\avaliacao\avaliar_imagem.py" --execucao $Inspecao
```

### Gerar novamente um PDF

Os batches geram seus PDFs automaticamente. Para repetir apenas o relatório,
use o comando correspondente; substitua os caminhos entre `<...>` por pastas
reais, sem os sinais de menor e maior:

```powershell
# Rodadas ou seleção original em imagens
& $PythonTcc ".\scripts\avaliacao\gerar_relatorio_rodada.py" --batch "<pasta do batch de imagens>"

# Reavaliação por indivíduos
& $PythonTcc ".\scripts\limiarizacao\reavaliar_selecao.py" --somente-relatorio "<pasta da reavaliação>"

# Vídeos de seleção ou finais; a pasta identifica a etapa
& $PythonTcc ".\scripts\limiarizacao\executar_videos.py" --somente-relatorio "<pasta do batch de vídeos>"
```

Cada geração cria outra pasta de relatório e preserva as métricas do experimento.
Para rodadas e seleção em imagens, use o batch completo, incluindo as pastas de
configuração referenciadas, e não apenas uma cópia isolada dos resumos.

### Executar os testes de código

Depois da instalação das dependências, os testes podem ser executados antes
dos experimentos:

```powershell
& $PythonTcc -m unittest discover -s analise -p "test_*.py"
& $PythonTcc -m unittest discover -s scripts/testes -p "test_*.py"
```

Os testes verificam métricas, planos, integridade e interfaces de execução;
não substituem a avaliação experimental dos detectores. Para consultar os
argumentos de um script, acrescente `--help` ao comando.

## Documentação técnica

- [Conclusão da limiarização: seleção e avaliação final](analise/conclusao_limiarizacao.md).
- [Plano de avaliação de blobs e adaptações do ciclo](analise/plano_blobs.md).
- [Executar a inspeção inicial de blobs (round0)](scripts/blobs/README.md).
- [Protocolo e fluxograma completo](analise/protocolo_rodadas.md).
- [Guia dos scripts](scripts/README.md).
- [Parâmetros e saídas da limiarização](scripts/limiarizacao/README.md).
- [Contrato dos detectores clássicos](algoritmos/classicos/README.md).
- [Métricas e relatórios](analise/README.md).
- [Revisões e resultados das rodadas](analise/rodadas/).
