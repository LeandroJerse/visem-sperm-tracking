# Catálogo analítico

O SQLite é uma cópia derivada dos CSVs, JSONs e manifestos existentes em
`../tests/` e `../results/`. Ele nunca é a fonte primária dos resultados.

- `legacy/visem.db`: banco anterior à reorganização, preservado para auditoria;
- `visem.db`: destino do banco regenerado com os caminhos canônicos.

O banco canônico foi regenerado em 2026-08-29 e preservou exatamente as quatro
tabelas legadas (`372.142` detecções, `7` resumos, `85` linhas clínicas e
`29.196` contagens GT), acrescentando `11` runs e suas métricas/custos. As
`11/11` runs possuem `configuration_id` e `configuration_hash` preenchidos, e
a auditoria encontrou `0` referências de artefato quebradas depois da
resolução de caminhos históricos.

Essa resolução não reescreve os JSONs das runs: `src/core/relocation.py` usa
`data/manifests/layout_20260829.csv` somente durante a leitura. O banco continua
sendo derivado e pode ser reconstruído com
`python -m script.project.application.build_database`.
