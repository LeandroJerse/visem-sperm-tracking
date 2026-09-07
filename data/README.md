# Dados e artefatos experimentais

[Início do projeto](../README.md) · [Comandos que geram artefatos](../script/README.md)

## Encontre o que procura

| Procura | Abra |
|---|---|
| Imagens, tabelas e métricas do threshold | Caminho local `tests/detection/threshold/` |
| Ensaios Otsu separados do limiar fixo | Caminho local `tests/detection/otsu/` |
| Entender as pastas do frame a frame | [Guia de detecção](tests/detection/README.md) |
| Desenvolvimento das quatro tarefas | [tests/README.md](tests/README.md) |
| Seleções, testes confirmatórios e aplicação | [results/README.md](results/README.md) |
| Inventário, splits e lacunas | [manifests/](manifests/) |
| Intermediários recriáveis | [derived/](derived/) |
| Pesos de modelos | [models/](models/) |
| Banco analítico derivado | [catalog/](catalog/) |

Pastas de resultados podem conter apenas um README enquanto não há execução.
As runs e subpastas específicas são criadas pelos executores, conforme a etapa.
Os artefatos locais não acompanham o código versionado.
Código de teste fica em [tests/ na raiz](../tests/README.md); esta pasta guarda
dados e saídas, não implementações dos algoritmos.

## Estrutura

Esta é a única raiz para dados, modelos, testes e resultados do TCC. A
separação abaixo é metodológica: evita misturar fonte externa, derivado
recriável, busca de hiperparâmetros e resultado confirmatório.

```text
data/
├── sources/       datasets originais imutáveis
├── manifests/     inventários, splits, lacunas e mapas de migração
├── datasets/      definições de datasets derivados, como o YOLO
├── derived/       frames, anotações convertidas, tracks, fluxo e janelas
├── tests/         smoke, frame screening, tuning, treino e validação
├── results/       configuração congelada, teste, 5-fold e aplicação
├── models/        pesos externos ou modelos exportados
├── catalog/       banco SQLite analítico, sempre derivado
└── quarantine/    arquivos alheios aguardando remoção manual
```

## Regra de organização experimental

Tanto `tests/` quanto `results/` seguem:

```text
<domínio>/<algoritmo>/<configuração>/<etapa>/<run_id>/
```

- `tests/`: resultados usados para desenvolver ou escolher uma configuração;
- `results/`: somente decisões congeladas e avaliações fora da amostra;
- o vídeo, split, seed e estágio não definem uma configuração;
- cada run permanece imutável e contém seu próprio manifesto;
- comparações entre configurações ficam em `_comparisons/`.

Uma configuração promovida pode conter `selection/` diretamente sob sua pasta.
Esse diretório é um registro de decisão, não uma run: referencia a validação e
o YAML congelado. Toda execução continua obrigatoriamente sob
`<etapa>/<run_id>/`.

Os 20 vídeos anotados estão em
`sources/visem_tracking/dataset/Train/`. Os 85 vídeos originais estão em
`sources/visem/videos/`. Os 502 clipes são derivados e ficam em
`derived/clips/`; eles não são amostras independentes.

Consulte `manifests/layout_20260829.csv` para mapear qualquer caminho antigo
para o novo destino.
