# Limiarização: execução e detalhes das saídas

Para escolher o comando, consulte o [guia de scripts](../README.md).
Todos os comandos abaixo são executados na raiz do projeto.

O [protocolo de desenvolvimento por rodadas](../../analise/protocolo_rodadas.md)
registra o fluxo de preparação, execução, avaliação e revisão conjunta.

## Primeira rodada em batch

O plano `scripts/limiarizacao/rodadas/round1.json` contém as 48 configurações
completas da primeira rodada, geradas com seed **42**. São 24 manuais e 24 Otsu,
com 12 configurações por combinação de método e polaridade. A configuração
`c01` repete os parâmetros do teste inicial como referência.

Todas usam os mesmos **178 quadros anotados** dos 12 vídeos de desenvolvimento.
Os quadros 900 e 1100 do vídeo 23 foram explicitamente excluídos por ausência
de anotação, conforme acordado; não são tratados como imagens sem objetos.
As demais imagens seguem os quadros 0, 100, ..., 1400. São 8.544 avaliações de
imagem, com uma comparação PNG por avaliação. Reserve espaço para essas mídias.

Para executar, abra o terminal na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_rodada.py" --rodada round1
```

Um único executor atende às rodadas: `--rodada round1` carrega
`scripts/limiarizacao/rodadas/round1.json`. Sem argumentos, também usa `round1`.
As rodadas 2 e 3 ainda não têm planos preparados. Para usar um plano em outro
local, informe `--plano` em vez de `--rodada`. Caso falte alguma dependência,
instale no mesmo Python e repita o comando:

```powershell
& "C:\Python313\python.exe" -m pip install -r ".\algoritmos\classicos\requirements.txt" -r ".\analise\requirements.txt" -r ".\analise\requirements-relatorio.txt"
```

O PDF utiliza Matplotlib e ReportLab. O executor verifica essas dependências
antes de iniciar as detecções. A instalação e as execuções são realizadas
pelo pesquisador no mesmo ambiente Python.

O executor confere o plano e os hashes das entradas antes de detectar. Durante
o processamento, verifica novamente o conteúdo de cada entrada. Um arquivo
alterado, ausente ou inválido interrompe a execução; não há exclusão automática.
Os vídeos de seleção e avaliação final não são aceitos neste executor.

Cada configuração produz detecções e calcula as métricas já acordadas: IoU
>= 0,50, associação única por classe, precisão, recall, F1, macro-F1 e análise
auxiliar de localização. Os resultados são agregados somando TP/FP/FN antes
de calcular F1. Não se calcula a média dos F1 dos quadros.

```text
resultados/frame-to-frame/limiarizacao/round1/
├── batch__<data-hora-UTC>/
│   ├── rodada.json
│   ├── execucao.json
│   ├── codigo.zip
│   ├── resumo_configuracoes.csv
│   ├── resumo_por_video.csv
│   └── relatorios/<data-hora-UTC>/
│       ├── relatorio.pdf
│       ├── relatorio.json
│       └── execucao_origem.json
└── <configuracao>__<data-hora-UTC>/
    ├── configuracao.json
    ├── execucao.json
    ├── deteccoes.csv
    ├── anotacoes.csv
    ├── por_quadro.csv
    ├── metricas_por_quadro.csv
    ├── metricas_por_video.csv
    ├── metricas.csv
    ├── avaliacao.json
    ├── pares.csv
    ├── pendentes.csv
    ├── predicoes/<video>_frame_<quadro>.txt
    └── midia/<video>_frame_<quadro>__comparacao.png
```

`resumo_configuracoes.csv` reúne os resultados das configurações concluídas,
na ordem do plano. `resumo_por_video.csv` permite verificar a variação entre
vídeos. O script não escolhe automaticamente configurações para a próxima
rodada nem as cinco finalistas. As decisões serão tomadas com o pesquisador.

Para consultar o resultado principal, abra `resumo_configuracoes.csv` e
localize a coluna `macro_f1`. Os F1 por classe estão em `f1_classe_0`,
`f1_classe_1` e `f1_classe_2`. `f1_localizacao` é o diagnóstico que ignora a
classe, não a métrica principal. `configuracao_id` identifica o teste e
`pasta` indica onde estão seus parâmetros, tabelas detalhadas e imagens.

`pares.csv` e `pendentes.csv` distinguem as avaliações principal e auxiliar
pela coluna `avaliacao`. Índices de objetos valem somente para o respectivo
vídeo/quadro. F1 sem casos fica vazio nos CSV, com situação `sem_casos`; no
JSON, fica `null`. As coordenadas e áreas continuam em pixels.

O tempo registrado mede uma chamada ao detector por imagem, sem cache de
detecções; exclui leitura, avaliação e gravação. OpenCV usa uma thread e
OpenCL desativado. Essa medição é diagnóstica, varia entre execuções e não
implementa ainda o desempate por desempenho.

### Relatório PDF automático

Ao concluir o batch, o executor gera o relatório a partir das tabelas salvas.
Para até 48 configurações e 12 vídeos, o PDF apresenta três páginas: macro-F1 de todas as
configurações, F1 das três classes e macro-F1 por vídeo. A ordenação visual
facilita a leitura e não seleciona as cinco finalistas.

As estatísticas descritivas mostram média, mediana, desvio padrão amostral,
mínimo, máximo e quantidade de valores definidos entre as configurações.
Não representam intervalo de confiança nem prova de superioridade. Não se
calcula a média dos F1 dos quadros para obter o F1 de uma configuração.
Valores `sem_casos` continuam distintos de zero.

Cada geração cria `relatorios/<data-hora-UTC>/`, sem sobrescrever PDFs
anteriores. `relatorio.json` registra a geração e `execucao_origem.json`
preserva o registro da execução utilizada. O estado do relatório fica
separado do estado da detecção: uma falha no PDF preserva as métricas já
concluídas. É possível gerar o relatório depois, sem repetir o batch.

Para a primeira rodada já executada, instale as dependências do relatório e
gere somente o PDF, na raiz do projeto:

```powershell
& "C:\Python313\python.exe" -m pip install -r ".\analise\requirements-relatorio.txt"
& "C:\Python313\python.exe" ".\scripts\avaliacao\gerar_relatorio_rodada.py" --batch ".\resultados\frame-to-frame\limiarizacao\round1\batch__20260919T192640642218Z"
```

Para outra execução, substitua o caminho de `--batch` pela pasta que contém
`resumo_configuracoes.csv` e `resumo_por_video.csv` daquela execução. Não
informe a pasta inteira do `round` nem a pasta de uma configuração isolada.
O gerador do relatório foi conferido estaticamente. O pesquisador o executa;
a apresentação visual do primeiro PDF ainda precisa ser conferida.

### Repetição e seed

Para repetir a primeira rodada, execute o mesmo comando. O programa lê as
configurações já salvas; não faz novo sorteio nem preenche parâmetros com base
nos resultados anteriores. A pasta `round1` é preservada e recebe novas
execuções com data/hora distinta. Uma falha preserva os arquivos parciais e
marca a execução como `falhou`; repetir começa uma execução completa, sem
retomar ou misturar dados parciais.

Também é possível repetir a cópia do plano guardada em um batch:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_rodada.py" --plano ".\resultados\frame-to-frame\limiarizacao\round1\batch__<data-hora-UTC>\rodada.json"
```

A seed controla a geração das combinações; manual e Otsu não sorteiam novos
parâmetros durante a detecção. O plano guarda configurações, ordem dos quadros
e hashes de imagens/anotações. A execução guarda versões, hashes do código e
uma cópia dos fontes em `codigo.zip`. Reproduzir resultados requer conservar
as entradas, o código e o ambiente, não apenas a seed; horários e tempos de
processamento naturalmente diferem.

`preparar_rodada.py` permite reconstruir o sorteio sem executar
detectores, mas **não é necessário para executar a rodada já preparada**:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\preparar_rodada.py" --seed 42 --rodada round1 --saida "scripts/limiarizacao/rodadas/round1_reproduzida.json"
```

O plano da primeira rodada foi apenas movido para `rodadas/round1.json`,
sem alterar seu conteúdo. O caminho e o hash do gerador permanecem como
registro histórico da preparação original. O gerador atual está em
`preparar_rodada.py`; novos planos registram a versão atual. Para repetir a
rodada existente, use `executar_rodada.py` com o plano salvo.

O gerador exige um arquivo novo, não sobrescreve planos e registra sua versão
e a versão do Python. Seu espaço é o da exploração inicial. As rodadas 2 e 3
dependem da análise conjunta dos resultados; não estão pré-selecionadas.

| Parâmetro explorado | Valores da primeira rodada |
|---|---|
| Limiar manual | 60, 90, 120, 150, 180, 210; cada um duas vezes por polaridade |
| Polaridade | Claro e escuro |
| Abertura e fechamento | Desativados, elipse 3 × 3 ou 5 × 5 com uma iteração |
| Área mínima | 1, 3, 6, 12, 24 pixels |
| Máximo da classe pequena | 20, 40, 80, 120 pixels |
| Mínimo da classe aglomerado | 150, 250, 400, 600, 1000 pixels |
| Fixos | Conectividade 8; sem área máxima |

Os valores são hipóteses exploratórias. Não foram escolhidos por desempenho.
A amostragem é sem configurações duplicadas e preserva uma faixa possível
para a classe pequena (`area_minima <= area_maxima_pequeno`).

### Testes do código

O código foi conferido estaticamente. A execução do batch e dos testes cabe
ao pesquisador. Testes sintéticos de agregação e integridade do plano:

```powershell
& "C:\Python313\python.exe" -m unittest analise.test_avaliacao_deteccao analise.test_agregacao_deteccao scripts.testes.test_plano_limiarizacao
```

## Execução individual em imagem

`inspecionar_imagem.py` recebe uma imagem, sua anotação e uma configuração.
Executa a variante manual ou Otsu e grava uma comparação visual e tabelas.
As execuções serão feitas pelo pesquisador. O script foi revisado estaticamente
e o pesquisador realizou uma primeira inspeção individual do quadro 0 do vídeo 11.
O resultado dessa inspeção não valida o detector experimentalmente.

As primeiras inspeções devem usar imagens do conjunto de desenvolvimento.
O script registra `inspecao_individual`, não atribui automaticamente a entrada
a um conjunto do protocolo e não bloqueia arquivos de outros conjuntos.

Não calcula IoU, precisão, recall ou F1, não escolhe parâmetros e não executa
lotes, vídeos ou seleção das melhores configurações. As contagens exportadas
descrevem as saídas; não representam acertos.

Para calcular as métricas de uma execução já salva, use o script separado
[`avaliacao/avaliar_imagem.py`](../avaliacao/avaliar_imagem.py), descrito em
[`analise/README.md`](../../analise/README.md).
Não é necessário repetir a detecção. O avaliador foi escrito e revisado
estaticamente; sua execução e a dos testes sintéticos cabem ao pesquisador.

## Preparação

Abra o terminal na raiz do projeto. É necessário Python 3.10 ou posterior.
Use o mesmo ambiente Python na instalação e na execução:

```powershell
python -m pip install -r algoritmos/classicos/requirements.txt
```

Copie `scripts/configuracoes/limiarizacao.modelo.json` para
`scripts/configuracoes/minha_configuracao.json` e preencha os campos. O modelo
foi originalmente entregue incompleto e pode ter sido preenchido localmente
para a primeira inspeção. Os valores usados nessa inspeção são provisórios.
O script informa campos obrigatórios ainda nulos e interrompe a execução.
JSON não aceita comentários; textos precisam de aspas duplas.

| Campo | Preenchimento |
|---|---|
| `metodo` | `"manual"` ou `"otsu"` |
| `polaridade` | `"claro"` seleciona pixels acima do limiar; `"escuro"`, até o limiar |
| `limiar_manual` | Inteiro de 0 a 255 para manual; `null` para Otsu |
| `abertura.forma`, `fechamento.forma` | `"elipse"`, `"retangulo"` ou `"cruz"` |
| `abertura.tamanho`, `fechamento.tamanho` | Inteiro positivo ímpar; largura e altura do elemento em pixels |
| `abertura.iteracoes`, `fechamento.iteracoes` | Inteiro não negativo; zero desativa a respectiva operação |
| `conectividade` | 4 ou 8 |
| `area_minima` | Inteiro positivo; regiões menores são descartadas |
| `area_maxima` | Inteiro maior ou igual à área mínima; `null` desativa o limite superior |
| `classificacao.area_maxima_pequeno` | Inteiro positivo; até esse valor, inclusive, classe 2 |
| `classificacao.area_minima_aglomerado` | Inteiro pelo menos duas unidades acima do limite pequeno; a partir dele, classe 1 |

Os campos de forma e tamanho precisam ser preenchidos mesmo quando a operação
está desativada. Somente `limiar_manual` em Otsu e `area_maxima` sem limite
superior podem permanecer `null`. A faixa intermediária da classificação é a
classe 0. As áreas se referem aos pixels da região após a morfologia.

Os valores serão discutidos e avaliados no conjunto de desenvolvimento.
Preencher uma configuração não significa que ela está calibrada ou validada.

## Comando

Após preencher a configuração, este comando utiliza o quadro 0 do vídeo 11,
pertencente ao conjunto de desenvolvimento:

```powershell
python scripts/limiarizacao/inspecionar_imagem.py --imagem "bases_de_dados/visem_tracking/dataset/Train/11/images/11_frame_0.jpg" --anotacao "bases_de_dados/visem_tracking/dataset/Train/11/labels/11_frame_0.txt" --config "scripts/configuracoes/minha_configuracao.json"
```

Para consultar os argumentos sem executar o detector:

```powershell
python scripts/limiarizacao/inspecionar_imagem.py --help
```

Os caminhos de entrada relativos são interpretados a partir da pasta atual
do terminal. Caminhos com espaços devem ficar entre aspas. A saída sempre
fica na pasta `resultados/` deste projeto, independentemente da pasta do terminal.

A imagem deve ser uint8 em cinza ou BGR com três canais. A leitura preserva a
orientação armazenada dos pixels, sem aplicar rotação automática por EXIF.
Imagens com transparência ou profundidade diferente de 8 bits são rejeitadas.

A anotação deve vir de `labels/`, com cinco campos por linha:

```text
class_id center_x center_y width height
```

Imagem e anotação devem ter o mesmo nome-base, como `11_frame_0`. Essa conferência
evita trocas de nomes, mas não verifica visualmente se os arquivos correspondem.
As classes aceitas são 0, 1 e 2. As coordenadas precisam ser finitas e normalizadas,
com caixas de tamanho positivo dentro da imagem. Há tolerância de `1e-8` apenas
para arredondamento decimal nas bordas. As coordenadas originais são preservadas
na tabela; a conversão para pixels inteiros ocorre somente no desenho.

Arquivo de anotação existente e vazio é aceito como zero anotações. Arquivo
ausente interrompe a execução; nunca é convertido implicitamente em vazio.
Arquivos de `labels_ftid/`, com seis campos, são rejeitados neste script.

## Resultados

```text
resultados/frame-to-frame/limiarizacao/
└── round0/<resumo>__cfg-<hash>__<data-hora-UTC>/
    ├── configuracao.json
    ├── execucao.json
    ├── deteccoes.csv
    ├── anotacoes.csv
    ├── predicoes.txt
    ├── por_quadro.csv
    └── midia/
        └── <imagem>__comparacao.png
```

- **Comparação:** anotações à esquerda e detecções à direita, sem redimensionar
  a imagem. As mesmas cores e números identificam as classes nos dois painéis.
  A legenda e as contagens aparecem acima das imagens. Caixas sobrepostas
  permanecem presentes; não há remoção de duplicidades da anotação.
- **`configuracao.json`:** configuração completa efetivamente entregue ao detector,
  no mesmo formato aceito em `--config`; pode ser reutilizada.
- **`execucao.json`:** situação, horários UTC, origem, hashes dos arquivos de
  entrada, configuração, código, commit quando disponível, versões e unidades.
  Os hashes dos arquivos Python identificam também alterações ainda não commitadas.
- **`deteccoes.csv`:** uma linha por detecção, com classe, caixa em pixels e
  normalizada, centroide, áreas, alongamento da caixa, ocupação e intensidade.
- **`anotacoes.csv`:** uma linha por anotação, incluindo a linha de origem e
  as coordenadas normalizadas originais e convertidas para pixels.
- **`predicoes.txt`:** previsões no formato de cinco campos usado em `labels/`.
- **`por_quadro.csv`:** resumo da imagem, contagens totais e por classe e limiar usado.

As tabelas têm cabeçalho mesmo quando não há objetos. O resumo mantém uma linha
para a imagem, inclusive com zero detecções. Os CSV usam vírgula como separador,
ponto decimal e UTF-8 com BOM. No Excel, se necessário, use a importação
**Dados → De Texto/CSV** e selecione vírgula como delimitador.

O script individual usa `round0` por padrão. Para atribuir a inspeção a outra
rodada, informe `--rodada round1`, por exemplo. Ele não move resultados antigos.

O padrão `<video>_frame_<quadro>` do nome da imagem permite registrar a origem
do quadro. Para outros nomes, vídeo e quadro ficam vazios. Tempo em segundos
permanece vazio: este script não conhece a taxa de quadros. O índice da detecção
vale apenas dentro da imagem e não representa identidade entre quadros.

O resumo do nome inclui variante, polaridade e morfologia. `ab` significa
abertura; `fe`, fechamento; `e`, elipse; `r`, retângulo; `c`, cruz. Após a forma,
aparecem tamanho e iterações, separados por `x`. O hash usa todos os parâmetros,
inclusive os limites de área, evitando depender de nomes excessivamente longos.
São usados 12 caracteres do hash no nome e o SHA-256 completo nos metadados.
A data UTC inclui microssegundos. Uma colisão interrompe a execução sem sobrescrever.

Uma pasta só está completa quando `execucao.json` indica `"situacao": "concluida"`.
Falhas tratadas ficam registradas como `"falhou"`; encerramento abrupto pode
deixar `"em_andamento"`. Arquivos parciais são preservados para diagnóstico.
Os horários registrados não constituem uma medição de desempenho do detector.

Os arquivos originais são somente lidos. As anotações não são passadas ao
detector; servem à comparação visual e à exportação da referência.
