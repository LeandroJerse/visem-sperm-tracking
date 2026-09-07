# Dados derivados

Artefatos recriáveis gerados a partir de `../sources/`:

- `clips/`: clipes de 30 segundos, nunca contados como vídeos independentes;
- `detection/`: frames extraídos e anotações normalizadas;
- `tracking/`: trajetórias exportadas;
- `flow/`: campos de movimento aparente cacheados;
- `prediction/`: janelas de histórico e futuro.

## Inspeção das anotações

A retomada de setembro de 2026 começa pelo
[guia de inspeção de anotações](detection/annotation_audit/README.md).
As imagens com caixas manuais, tabelas de coordenadas e manifestos ficam em
`detection/annotation_audit/<audit_id>/video_<id>/frame_<indice>/`.
São derivados para conferir o gabarito, sem execução ou métricas de detector.

Os experimentos anteriores permanecem preservados em `../tests/` e
`../results/`, com seus identificadores e manifestos originais. Esta retomada
não apaga nem sobrescreve fontes, configurações ou resultados históricos.

Resultados de experimentos não ficam aqui: use `../tests/` ou `../results/`.
