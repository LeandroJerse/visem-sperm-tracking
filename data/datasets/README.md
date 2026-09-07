# Definições de datasets derivados

Esta pasta guarda listas, descritores e splits materializados a partir de
`../sources/`. Ela não contém resultados experimentais.

- `yolo/official_12_4_4/`: descritor oficial gerado por vídeo;
- `yolo/legacy_16_4/`: split piloto antigo, preservado apenas para auditoria.

Arquivos gerados precisam registrar a origem e nunca podem misturar frames do
mesmo vídeo entre treino, validação e teste.
