# Guia dos scripts

**Próxima execução: inspeção inicial de blobs (`round0`).** O detector e o
plano fixo estão preparados; a execução com a base ainda está pendente.
Instale as dependências indicadas no [guia de blobs](blobs/README.md) e execute
na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_inspecao.py"
```

São seis imagens de desenvolvimento e duas configurações de sondagem,
gerando comparações visuais, tabelas, avaliação e PDF. O objetivo é verificar
caixas e medidas antes de definir o `round1`; ainda não há ranking de seleção.
O [plano de blobs](../analise/plano_blobs.md) explica os ajustes no ciclo.

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

Para blobs, use [executar_inspecao.py](blobs/executar_inspecao.py), conforme o
[guia de round0](blobs/README.md). Os scripts abaixo pertencem à limiarização.

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
