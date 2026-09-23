# Guia dos scripts

**Etapa atual: vídeos de seleção de watershed preparados para execução.**
A [análise](../analise/analise_selecao_watershed.md) fundamentou a aprovação
de s063, s064, s061, s062 e s098. Não é necessário repetir a seleção em imagens.
Próximo comando, na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_videos.py" --etapa selecao
```

São 29.250 avaliações, vinte vídeos comparativos e PDF automático de quatro
páginas. A opção `--conferir` verifica entradas e metadados sem executar o detector.
O [plano](../analise/plano_videos_watershed.md) descreve parâmetros e saídas.
Os vídeos finais serão preparados após a revisão desta execução.
Veja o [guia de watershed](watershed/README.md). Blobs está
[concluído, incluindo os vídeos finais](../analise/conclusao_blobs.md).
Os comandos abaixo reproduzem etapas anteriores.

**Blobs: cinco rodadas e seleção em imagens concluídas e analisadas.**
As 7.140 avaliações da seleção foram conferidas. A
[análise](../analise/analise_selecao_blobs.md) fundamentou a aprovação de
s052, s082, s084, s103 e s051. **Os vídeos completos de seleção foram concluídos
e conferidos**, com F1 0,668702 para s052. Veja a
[análise dos vídeos](../analise/analise_videos_selecao_blobs.md).
Veja a [análise do round5](../analise/analise_round5_blobs.md) e o
[documento completo do desenvolvimento](../analise/desenvolvimento_blobs.html).
A avaliação final foi concluída nos vídeos **14, 24, 38 e 82**.
Para reproduzi-la, na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_videos.py" --etapa final
```

Esse comando executa 29.550 avaliações e gera vinte vídeos, tabelas e PDF,
preservando tentativas anteriores. Acrescente `--conferir` para apenas conferir
as entradas, metadados e dependências, sem executar detecções. O
[guia de blobs](blobs/README.md) explica as saídas, os testes e a regeneração
do PDF. O round0 e seu [diagnóstico](../analise/diagnostico_round0_blobs.md)
estão concluídos. A [justificativa do round1](../analise/plano_round1_blobs.md)
descreve as 12 comparações controladas e as 36 configurações exploratórias.

O round5 terminou íntegro e os controles reproduziram o round4. São 119
configurações distintas no conjunto das cinco rodadas. A
[seleção em imagens está concluída](../analise/analise_selecao_blobs.md).
O [plano dos vídeos](../analise/plano_videos_blobs.md) descreve as conferências
e saídas em `resultados/videos/blobs/selecao/`, com as fontes em `origens/`.
Não é necessário repetir a seleção. O [plano final](../analise/plano_videos_final_blobs.md)
preserva as cinco configurações e salva em `resultados/videos/blobs/final/`,
também com as fontes em `origens/`. Essa etapa já foi executada e conferida.
Para repetir uma rodada concluída, use `executar_rodada.py --rodada round1`
até `--rodada round5`; isso não é necessário para a seleção.

**Limiarização concluída, incluindo a avaliação final.** Consulte a
[análise consolidada](../analise/conclusao_limiarizacao.md). Os comandos abaixo
permitem reproduzir suas etapas já concluídas.

Para repetir a avaliação final, abra o PowerShell na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_videos.py" --etapa final
```

A seleção em imagens e a reavaliação das **122 configurações × 60 quadros**
foram concluídas, assim como o teste das cinco nos vídeos 13, 29, 52 e 54.
Após a revisão, foram congeladas **s068, s067, s090, s099 e s101** para os
vídeos finais **14, 24, 38 e 82**. O comando processa **5.910 quadros por
configuração**, com parâmetros e critérios preservados no
[plano final](limiarizacao/videos/plano_final.json).

São gerados **20 MP4 comparativos**: anotações da base à esquerda e detecções
à direita. Tabelas, ranking e PDF acompanham os vídeos em
`resultados/videos/limiarizacao/final/batch__<data-hora-UTC>/`.
O F1 de indivíduos (0 e 2) continua sendo o critério principal; trocas de
classificação e aglomerados (1) são registrados separadamente.
Antes da detecção, o executor verifica arquivos e alinhamento temporal.
O batch final `batch__20260920T030805588232Z` concluiu as 29.550 avaliações,
os vídeos e o PDF; contagens e hashes foram conferidos. Os testes de código
não foram executados nesta revisão documental.
Repetições criam novas pastas e preservam o histórico. Detalhes, dependências
e comandos de relatório estão no [guia de limiarização](limiarizacao/README.md).

**Sem `--etapa final`, o comando continua executando a seleção.** Para repetir
explicitamente a etapa concluída, use `executar_videos.py --etapa selecao`.
O mesmo script atende às duas etapas; cada uma tem seu plano e sua pasta.

Para repetir somente a reavaliação das caixas salvas das imagens:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\reavaliar_selecao.py"
```

Esse comando mantém como origem o batch `batch__20260920T012713968145Z` e
cria `reavaliacoes_individuos/<execucao>/` dentro dele, sem repetir a detecção.
As cinco rodadas anteriores já foram executadas e permanecem disponíveis com
`executar_rodada.py --rodada round1` até `--rodada round5`.
**Sem argumentos, `executar_rodada.py` ainda usa round1.**

**Onde ver o F1:** `ranking.csv`, coluna `f1_individuos`, na pasta do batch de
vídeos após sua execução. Para as imagens, consulte
`reavaliacoes_individuos/<execucao>/ranking.csv` dentro do batch de seleção.
Na respectiva pasta, `resumo_configuracoes.csv` traz cobertura e
classificação; `resumo_por_video.csv` mostra a variação entre vídeos.
O PDF fica em `relatorios/<data-hora-UTC>/relatorio.pdf` dentro da execução.
Os resumos e PDFs das rodadas e da seleção original continuam usando
macro-F1 das três classes.

## Qual script usar?

Para blobs, use [executar_videos.py](blobs/executar_videos.py) na etapa atual;
[executar_selecao.py](blobs/executar_selecao.py) reproduz a seleção em imagens;
[executar_rodada.py](blobs/executar_rodada.py) reproduz o desenvolvimento;
[diagnosticar_round0.py](blobs/diagnosticar_round0.py) analisa a inspeção concluída
e [executar_inspecao.py](blobs/executar_inspecao.py) repete sua detecção original.
Consulte o [guia](blobs/README.md).
Os scripts abaixo pertencem à limiarização.

| O que você quer fazer | Script | Quando usar |
|---|---|---|
| Repetir a avaliação das cinco configurações em vídeos completos | [limiarizacao/executar_videos.py](limiarizacao/executar_videos.py) | `--etapa final` ou `--etapa selecao`: etapas concluídas; `--somente-relatorio`: outro PDF |
| Repetir a reavaliação das caixas salvas | [limiarizacao/reavaliar_selecao.py](limiarizacao/reavaliar_selecao.py) | Etapa já concluída; também regenera seu PDF com `--somente-relatorio` |
| Repetir a detecção nas imagens de seleção | [limiarizacao/executar_selecao.py](limiarizacao/executar_selecao.py) | Execução original já concluída; preserva avaliação histórica por três classes |
| Executar e avaliar uma rodada completa | [limiarizacao/executar_rodada.py](limiarizacao/executar_rodada.py) | Comando principal dos batches; a avaliação já está incluída |
| Inspecionar uma única imagem | [limiarizacao/inspecionar_imagem.py](limiarizacao/inspecionar_imagem.py) | Comparação visual e tabelas, com imagem, anotação e configuração informadas |
| Avaliar uma inspeção individual já salva | [avaliacao/avaliar_imagem.py](avaliacao/avaliar_imagem.py) | Calcula as métricas de uma imagem; não é necessário depois do batch |
| Gerar o PDF de uma rodada já concluída | [avaliacao/gerar_relatorio_rodada.py](avaliacao/gerar_relatorio_rodada.py) | Usa os resultados salvos, sem repetir as detecções |
| Preparar a exploração inicial | [limiarizacao/preparar_rodada.py](limiarizacao/preparar_rodada.py) | Sorteia o espaço inicial; não reconstrói `round2`/`round3`/`round4`/`round5` e não é necessário para executar planos salvos |

**A rodada é identificada pelo plano JSON, não por uma cópia do script.**
`round1.json`, `round2.json`, [round3.json](limiarizacao/rodadas/round3.json),
[round4.json](limiarizacao/rodadas/round4.json) e
[round5.json](limiarizacao/rodadas/round5.json) estão prontos.
Os quatro últimos são listas determinísticas definidas pela análise,
sem novo sorteio; a seed 42 permanece apenas como registro. Estão previstas
cinco rodadas de desenvolvimento, já concluídas. As 122 configurações distintas
foram comparadas na seleção; as cinco candidatas para vídeos foram aprovadas
após a revisão da reavaliação. Nenhum batch promove candidatos automaticamente.
A avaliação final é identificada por `--etapa final`.
`round0` reúne as inspeções iniciais
e fica fora dessa contagem.

```text
scripts/
├── blobs/
│   ├── executar_videos.py         etapa atual; vídeos de seleção/final e PDF
│   ├── videos/plano_selecao.json  cinco configurações aprovadas e quatro vídeos
│   ├── videos/plano_final.json    mesmas cinco e quatro vídeos finais
│   ├── planejamento_videos_final.py  geração e validação do plano final
│   ├── planejamento_videos.py     geração e validação do plano de vídeos
│   ├── executar_selecao.py        reprodução da seleção em imagens
│   ├── selecao/plano.json         119 configurações e 60 imagens
│   ├── executar_rodada.py         reprodução das cinco rodadas
│   ├── planejamento.py           geração e validação dos planos
│   ├── planejamento_round2.py    desenho do round2; módulo interno
│   ├── planejamento_round3.py    desenho do round3; módulo interno
│   ├── planejamento_round4.py    desenho do round4; módulo interno
│   ├── planejamento_round5.py    desenho do round5; módulo interno
│   ├── rodadas/round1.json        48 configurações congeladas
│   ├── rodadas/round2.json        32 configurações congeladas
│   ├── rodadas/round3.json        24 configurações congeladas
│   ├── rodadas/round4.json        18 configurações congeladas
│   ├── rodadas/round5.json        14 configurações congeladas
│   ├── executar_inspecao.py       reprodução do round0
│   ├── diagnosticar_round0.py     análise dos registros da inspeção
│   ├── inspecao/round0.json
│   └── README.md
├── limiarizacao/
│   ├── executar_rodada.py
│   ├── executar_selecao.py
│   ├── reavaliar_selecao.py
│   ├── executar_videos.py
│   ├── inspecionar_imagem.py
│   ├── preparar_rodada.py
│   ├── rodadas/round1.json
│   ├── rodadas/round2.json
│   ├── rodadas/round3.json
│   ├── rodadas/round4.json
│   ├── rodadas/round5.json
│   ├── selecao/plano.json
│   ├── videos/plano_selecao.json
│   ├── videos/plano_final.json
│   └── README.md                 detalhes e demais comandos
├── avaliacao/
│   ├── avaliar_imagem.py
│   └── gerar_relatorio_rodada.py
├── configuracoes/limiarizacao.modelo.json
└── testes/                       verificações dos planos e das entradas
```

O modelo em `configuracoes/` serve à inspeção individual. O batch usa as
configurações completas já salvas no plano da rodada.

Dependências, argumentos e arquivos gerados: [guia de limiarização](limiarizacao/README.md).
Regras das métricas: [guia de avaliação](../analise/README.md).
Fluxograma e decisões entre rodadas: [protocolo](../analise/protocolo_rodadas.md).

## Testes do código

`testes/` contém verificações do plano; os testes de métricas ficam em
`analise/`. Esses arquivos verificam o código e não executam uma rodada
experimental. O comando está na seção de testes do [guia de limiarização](limiarizacao/README.md).
Todas as execuções, inclusive testes, são realizadas pelo pesquisador.
