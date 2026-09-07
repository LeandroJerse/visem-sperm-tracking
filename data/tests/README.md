# Testes experimentais

[Mapa dos dados](../README.md) · [Executores](../../script/README.md)

| Tarefa | Artefatos de desenvolvimento | Implementações |
|---|---|---|
| Detecção | [detection/](detection/README.md) | [Código](../../src/detection/README.md) |
| Tracking | [tracking/](tracking/) | [Código](../../src/tracking/README.md) |
| Fluxo | [flow/](flow/) | [Código](../../src/flow/README.md) |
| Predição | [prediction/](prediction/) | [Código](../../src/prediction/README.md) |

Resultados de smoke tests, triagem frame a frame, tuning, treino e validação.
Eles podem selecionar uma configuração, mas não constituem por si só o
resultado confirmatório do TCC.

Estrutura obrigatória:

```text
<domínio>/<algoritmo>/<config_id>/<etapa>/<run_id>/
```

O conteúdo legado foi preservado e explicitamente marcado como `legacy` ou
`pilot`. Os 600 testes de threshold estão organizados por configuração em
`detection/threshold/` e `detection/otsu/`; as 60 imagens de entrada comuns
foram centralizadas em `detection/_shared_inputs/` sem perder os summaries.
