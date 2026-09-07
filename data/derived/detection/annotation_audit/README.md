# Inspeção de anotações

[Dados derivados](../../README.md) · [Inspeção de um quadro](../../../../script/README.md#inspecao-de-anotacoes) · [Auditoria do treino](../../../../script/README.md#geometria-das-anotacoes)

Esta área guarda a conferência visual de um quadro de treino e a auditoria
descritiva da geometria das anotações dos 12 vídeos de treino. O objetivo é
entender o gabarito antes de comparar detectores. Não contém execução de
detector, busca de parâmetros ou métricas de desempenho.

## Nível 1: inspeção de um quadro

```text
annotation_audit/
└── <audit_id>/
    └── video_<id>/
        └── frame_<indice>/
            ├── 00_quadro_original.png
            ├── 01_quadro_anotado.png
            ├── 02_exemplo_anotacao.png
            ├── annotations.csv
            └── manifest.json
```

O índice do quadro começa em zero e é escrito com seis algarismos no caminho.
A primeira inspeção da retomada usa
`retomada_20260907_nivel1/video_11/frame_000000/`.

| Arquivo local | Conteúdo |
|---|---|
| `00_quadro_original.png` | Quadro decodificado do MP4, sem marcações adicionadas |
| `01_quadro_anotado.png` | Mesmo quadro com caixas e centros das anotações manuais |
| `02_exemplo_anotacao.png` | Exemplo ampliado para explicar uma anotação |
| `annotations.csv` | Classes, identidades e coordenadas para conferência |
| `manifest.json` | Origem, identificação e informações de reprodução da inspeção |

Os números desenhados identificam as anotações apenas nesta figura. Os IDs
textuais originais são preservados na tabela; uma numeração visual não cria
uma trajetória nem verifica a continuidade da identidade.

Os artefatos são locais e ignorados pelo Git; este guia acompanha o código.
O executor aceita somente vídeos do treino e recusa sobrescrever uma saída
existente. Para outra inspeção, use uma identificação nova e mantenha a
anterior como registro. O comando é documentado apenas no
[guia oficial](../../../../script/README.md#inspecao-de-anotacoes).

## Limites da conferência

No quadro 0 do vídeo 11, os dois formatos originais de anotação contêm 43
caixas da classe 0, com as mesmas classes e coordenadas linha a linha; o
formato com identidades contém 43 IDs distintos. A classe 0, denominada
`normal` no dataset, não representa um diagnóstico clínico. Um `cluster`
representa agrupamento e não deve ser contado automaticamente como uma célula
individual; este quadro não contém anotações dessa classe.

Essa inspeção de um quadro não certifica a completude das anotações do
dataset, a continuidade dos IDs ou o desempenho de um algoritmo. O pesquisador
compreendeu o exemplo do nível 1 e aprovou priorizar a localização dos centros
na avaliação da detecção. Posteriormente, aprovou 10 px principal e 15/20 px
de sensibilidade obrigatória para todos os detectores, na resolução original
de 640 × 480 px. Essa decisão não autoriza uma busca de parâmetros nem
certifica o gabarito. Fontes, resultados e configurações históricas permanecem
preservados.

## Nível 2: geometria das anotações de treino

A auditoria descritiva usa exclusivamente os 12 vídeos do treino registrado.
Os arquivos de anotações são alinhados pelo número do frame; as dimensões vêm
dos cabeçalhos dos JPEGs, cujos bytes também são lidos para registrar hashes.
Nenhum vídeo é decodificado e nenhum detector é executado.

A saída local fixa fica em
`retomada_20260907_nivel2/treino_geometria/`. O
[comando oficial](../../../../script/README.md#geometria-das-anotacoes) recusa
uma pasta de saída existente. A reprodução exige uma cópia do repositório
com as fontes disponíveis e essa saída ausente; não apague o registro anterior
para refazer. Uma auditoria adicional precisa de outro destino, definido em
uma etapa própria. Os artefatos abaixo são locais e ignorados pelo Git.

| Arquivo local | Conteúdo |
|---|---|
| `per_frame_counts.csv` | Estado de anotação, disponibilidade de arquivos, dimensões, contagens brutas/válidas por classe e comparação dos formatos, por vídeo e frame |
| `per_video_geometry.csv` | Quantis de largura, altura, diagonal, meia diagonal e distância ao vizinho mais próximo, por vídeo e grupo |
| `per_video_gates.csv` | Frações geométricas para os raios 10, 15 e 20 px, com denominadores e contagens, por vídeo e grupo |
| `anomalies.csv` | Lacunas, problemas de formato/coordenadas/IDs, imagens indisponíveis e divergências entre formatos, preservando origem e detalhes |
| `input_files.csv` | Inventário dos arquivos lidos, com função, tamanho, data de modificação e hash SHA-256 |
| `summary.json` | Contagens por vídeo, tipos de anomalia e agregações das descrições por vídeo |
| `manifest.json` | Configuração, definições, limites, hashes, estado do Git, ambiente, hardware, tempo, memória e caminhos dos artefatos |
| `tolerancias_geometria.png` | Figura gerada em uma etapa de renderização separada, usando somente os CSVs derivados |
| `figure_manifest.json` | Proveniência da figura, separada do manifesto da auditoria |

A renderização tem um comando separado no mesmo
[guia oficial](../../../../script/README.md#geometria-das-anotacoes) e também
recusa sobrescrever seus arquivos. Ela não abre os dados-fonte.

O resumo desta auditoria registra 12 vídeos de treino, 17.466 frames anotados
e 368.487 observações válidas. Foram excluídos 174 frames sem anotação. Não
foram encontradas linhas geométricas inválidas nem divergências entre os dois
formatos de anotação comparados. Esses resultados não comprovam completude do
gabarito nem correção temporal das identidades.

As 17.466 entradas `unexpected_filename` em `anomalies.csv` correspondem a
arquivos auxiliares `.npy`, apenas enumerados e ignorados: não representam
linhas de anotação inválidas, e seu conteúdo não foi lido pela auditoria.

Uma **observação** é uma anotação válida em um frame anotado. Uma mesma
identidade pode aparecer em muitos frames; essas observações não representam
células distintas ou amostras estatísticas independentes. O resumo calcula
primeiro descrições por vídeo: medianas dos vídeos para dimensões/distâncias
e médias com peso igual por vídeo para frações, usando somente vídeos com
observações disponíveis no grupo.

Os grupos `class0`, `class1` e `class2` isolam cada classe do dataset.
`cells0_2` reúne as classes 0 e 2; `all` reúne 0, 1 e 2. O nome `cells0_2`
é apenas a identificação desse recorte. A classe 1 representa agrupamentos
e não deve ser interpretada como uma célula individual. A auditoria compara
esses recortes sem decidir a política de classes da avaliação futura.

A distância ao vizinho mais próximo é calculada entre centros do mesmo frame
e grupo. Quando há uma só anotação nesse grupo/frame, não há vizinho finito:
essa observação tem contagem própria e não entra nos quantis de distância.
As frações com sufixo `all` incluem todas as observações válidas do grupo;
as com sufixo `finite` usam somente as que têm vizinho finito.

Em `per_video_gates.csv`, `neighbor_le_radius` indica outro centro anotado
a uma distância de no máximo um raio; `neighbor_lt_2radius` indica distância
menor que dois raios, condição de sobreposição com área positiva entre discos
de tolerância. `radius_gt_half_diagonal` compara o raio com a distância do
centro ao canto da caixa. São relações geométricas das anotações, não taxas
de falsos positivos, erros de identidade ou prova de que um raio é adequado.

O formato com IDs (`labels_ftid`) é a referência desta auditoria. Sua ausência
marca o frame como `unlabeled`, excluído da geometria e nunca convertido em
negativo. Um arquivo existente vazio é `annotated_empty`. Anotações inválidas
são excluídas da geometria e registradas nas contagens e na tabela de anomalias,
sem corrigir ou recortar as fontes. Diferenças em relação ao formato sem IDs
são registradas para revisão, sem substituição silenciosa.

A decisão posterior à auditoria aprovou 10 px principal e 15/20 px de
sensibilidade obrigatória, com o identificador `center_distance_v2_10px`.
A avaliação anterior a 15 px tem a referência histórica
`center_distance_v1_15px`. Os CSVs, resumos, manifestos e a figura desta
auditoria não foram alterados por essa aprovação.

Trata-se de uma convenção operacional de localização, não de um raio ótimo
estimado. A auditoria não mede incerteza entre anotadores, completude do
gabarito ou continuidade dos IDs; o centro da caixa não é ponto anatômico
exato. A política posterior de classes e agrupamentos está descrita a seguir.
A interpretação da geometria e a decisão sobre o raio estão na
[tolerância espacial](../../../../docs/metodologia/TOLERANCIA_ESPACIAL.md).

## Nível 2: regiões de agrupamento

A nova auditoria usa os mesmos 12 vídeos, verificando os hashes e contagens
da geometria anterior. A pasta `retomada_20260907_nivel2/treino_agrupamentos/`
contém tabelas por vídeo e por quadro com cluster, exemplos determinísticos,
suas anotações, resumo, manifesto, índice das entradas e a figura
`agrupamentos_primeiros_quadros.png`. São artefatos locais, separados dos
anteriores e sem execução de detector.

Foram encontradas 5.413 observações cluster em 4.056 quadros dos vídeos
11, 12, 15 e 29; 4.250 centros individuais estão dentro dessas regiões.
A união exata das caixas, recortada à imagem, evita contar sobreposição em
dobro. As médias respeitam o vídeo como unidade e informam se incluem todos
os quadros anotados ou somente os que contêm agrupamentos.

O [comando oficial](../../../../script/README.md#agrupamentos-no-treino)
recusa sobrescrever a pasta. A interpretação, os denominadores e a política
v3 estão em [Classes e agrupamentos](../../../../docs/metodologia/CLASSES_E_AGRUPAMENTOS.md).
As auditorias de GT não medem desempenho nem promovem detectores.
