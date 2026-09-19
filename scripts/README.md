# Execução individual em imagem

`testar_limiarizacao_imagem.py` recebe uma imagem, sua anotação e uma configuração.
Executa a variante manual ou Otsu e grava uma comparação visual e tabelas.
As execuções serão feitas pelo pesquisador. O script foi revisado estaticamente;
a execução prática ainda está pendente.

As primeiras inspeções devem usar imagens do conjunto de desenvolvimento.
O script registra `inspecao_individual`, não atribui automaticamente a entrada
a um conjunto do protocolo e não bloqueia arquivos de outros conjuntos.

Não calcula IoU, precisão, recall ou F1, não escolhe parâmetros e não executa
lotes, vídeos ou seleção das melhores configurações. As contagens exportadas
descrevem as saídas; não representam acertos.

## Preparação

Abra o terminal na raiz do projeto. É necessário Python 3.10 ou posterior.
Use o mesmo ambiente Python na instalação e na execução:

```powershell
python -m pip install -r algoritmos/classicos/requirements.txt
```

Copie `scripts/configuracoes/limiarizacao.modelo.json` para
`scripts/configuracoes/minha_configuracao.json` e preencha os campos. O modelo
está intencionalmente incompleto: nenhum limite experimental foi escolhido.
O script informa os campos pendentes e interrompe a execução se receber o modelo
sem preenchimento. JSON não aceita comentários; textos precisam de aspas duplas.

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
python scripts/testar_limiarizacao_imagem.py --imagem "bases_de_dados/visem_tracking/dataset/Train/11/images/11_frame_0.jpg" --anotacao "bases_de_dados/visem_tracking/dataset/Train/11/labels/11_frame_0.txt" --config "scripts/configuracoes/minha_configuracao.json"
```

Para consultar os argumentos sem executar o detector:

```powershell
python scripts/testar_limiarizacao_imagem.py --help
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
└── <resumo>__cfg-<hash>__<data-hora-UTC>/
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
