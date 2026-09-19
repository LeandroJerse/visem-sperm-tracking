# Guia dos scripts

**Para executar a quarta rodada**, abra o PowerShell na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_rodada.py" --rodada round4
```

Esse comando executa e avalia as 18 configurações nos mesmos 178 quadros
aprovados (3.204 avaliações) e gera um PDF ao concluir. Antes da primeira
execução com relatório, instale as dependências indicadas no
[guia de limiarização](limiarizacao/README.md).
Os resultados ficam em `resultados/frame-to-frame/limiarizacao/round4/`.
Repetir o comando usa o mesmo plano e cria novas saídas, sem sobrescrever.
O motivo dos novos parâmetros está na [revisão do round3](../analise/rodadas/round3_revisao.md)
e a lista completa, no [plano do round4](limiarizacao/rodadas/round4.json).
As três rodadas anteriores já foram executadas e permanecem disponíveis com
`--rodada round1`, `--rodada round2` ou `--rodada round3`.
**Sem argumentos, o executor ainda usa round1.**

**Onde ver o F1:** abra `batch__<execucao>/resumo_configuracoes.csv` dentro
do respectivo `round`. `macro_f1` é a métrica principal; `f1_classe_0`,
`f1_classe_1` e `f1_classe_2` mostram cada classe. O PDF fica em
`batch__<execucao>/relatorios/<data-hora-UTC>/relatorio.pdf`.

## Qual script usar?

| O que você quer fazer | Script | Quando usar |
|---|---|---|
| Executar e avaliar uma rodada completa | [limiarizacao/executar_rodada.py](limiarizacao/executar_rodada.py) | Comando principal dos batches; a avaliação já está incluída |
| Inspecionar uma única imagem | [limiarizacao/inspecionar_imagem.py](limiarizacao/inspecionar_imagem.py) | Comparação visual e tabelas, com imagem, anotação e configuração informadas |
| Avaliar uma inspeção individual já salva | [avaliacao/avaliar_imagem.py](avaliacao/avaliar_imagem.py) | Calcula as métricas de uma imagem; não é necessário depois do batch |
| Gerar o PDF de uma rodada já concluída | [avaliacao/gerar_relatorio_rodada.py](avaliacao/gerar_relatorio_rodada.py) | Usa os resultados salvos, sem repetir as detecções |
| Preparar a exploração inicial | [limiarizacao/preparar_rodada.py](limiarizacao/preparar_rodada.py) | Sorteia o espaço inicial; não reconstrói `round2`/`round3`/`round4` e não é necessário para executar planos salvos |

**A rodada é identificada pelo plano JSON, não por uma cópia do script.**
`round1.json`, `round2.json`, [round3.json](limiarizacao/rodadas/round3.json) e
[round4.json](limiarizacao/rodadas/round4.json) estão prontos.
Os três últimos são listas determinísticas definidas pela análise,
sem novo sorteio; a seed 42 permanece apenas como registro. Estão previstas
cinco rodadas de desenvolvimento; o plano do round5 depende dos resultados
do round4 e não constitui avaliação final. `round0` reúne as inspeções iniciais
e fica fora dessa contagem.

```text
scripts/
├── limiarizacao/
│   ├── executar_rodada.py
│   ├── inspecionar_imagem.py
│   ├── preparar_rodada.py
│   ├── rodadas/round1.json
│   ├── rodadas/round2.json
│   ├── rodadas/round3.json
│   ├── rodadas/round4.json
│   └── README.md                 detalhes e demais comandos
├── avaliacao/
│   ├── avaliar_imagem.py
│   └── gerar_relatorio_rodada.py
├── configuracoes/limiarizacao.modelo.json
└── testes/test_plano_limiarizacao.py
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
