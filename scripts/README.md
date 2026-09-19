# Guia dos scripts

**Para executar a primeira rodada**, abra o PowerShell na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\limiarizacao\executar_rodada.py" --rodada round1
```

Esse comando executa e avalia as 48 configurações nos 178 quadros aprovados.
Os resultados ficam em `resultados/frame-to-frame/limiarizacao/round1/`.
Repetir o comando usa o mesmo plano e cria novas saídas, sem sobrescrever.

## Qual script usar?

| O que você quer fazer | Script | Quando usar |
|---|---|---|
| Executar e avaliar uma rodada completa | [limiarizacao/executar_rodada.py](limiarizacao/executar_rodada.py) | Comando principal dos batches; a avaliação já está incluída |
| Inspecionar uma única imagem | [limiarizacao/inspecionar_imagem.py](limiarizacao/inspecionar_imagem.py) | Comparação visual e tabelas, com imagem, anotação e configuração informadas |
| Avaliar uma inspeção individual já salva | [avaliacao/avaliar_imagem.py](avaliacao/avaliar_imagem.py) | Calcula as métricas de uma imagem; não é necessário depois do batch |
| Preparar um plano de configurações | [limiarizacao/preparar_rodada.py](limiarizacao/preparar_rodada.py) | Somente ao preparar um plano; não é necessário para executar `round1` |

**A rodada é identificada pelo plano JSON, não por uma cópia do script.**
`round1.json` já está pronto. Os planos de `round2` e `round3` serão definidos
após a análise conjunta; suas pastas de resultados não significam que os
planos já existam. `round0` reúne as inspeções individuais iniciais.

```text
scripts/
├── limiarizacao/
│   ├── executar_rodada.py
│   ├── inspecionar_imagem.py
│   ├── preparar_rodada.py
│   ├── rodadas/round1.json
│   └── README.md                 detalhes e demais comandos
├── avaliacao/avaliar_imagem.py
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
