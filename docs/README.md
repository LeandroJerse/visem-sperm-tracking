# Índice da documentação

[Início do projeto](../README.md) · [Implementações dos algoritmos](../src/README.md)

Esta pasta contém documentação científica e operacional. Código, configurações
e resultados não devem ser armazenados aqui.

## Projeto

- [`projeto/REVISAO_GERAL_20260908.md`](projeto/REVISAO_GERAL_20260908.md):
  auditoria de integridade e alinhamento com o projeto assinado, correções
  necessárias e limites das evidências atuais.

- [`projeto/MAPA_PROJETO.md`](projeto/MAPA_PROJETO.md): ponto de entrada e mapa
  de responsabilidades dos diretórios, dados, etapas e retomada do trabalho.
- [`projeto/MATRIZ_EXPERIMENTOS.md`](projeto/MATRIZ_EXPERIMENTOS.md): progresso
  algoritmo por algoritmo e etapa por etapa.
- [`projeto/DIARIO.md`](projeto/DIARIO.md): decisões e execuções em ordem
  cronológica.

## Metodologia

- [`metodologia/VALIDACAO_THRESHOLD_V3.md`](metodologia/VALIDACAO_THRESHOLD_V3.md):
  comparação prospectiva dos dois finalistas de treino nos quatro vídeos
  completos de validação, com controles de identidade e completude.

- [`metodologia/BUSCA_THRESHOLD_V3.md`](metodologia/BUSCA_THRESHOLD_V3.md):
  plano prospectivo da busca de threshold, amostra comum de treino, orçamento,
  classificação por vídeo, refinamento e evidências das execuções no treino.
- [`metodologia/PROTOCOLO.md`](metodologia/PROTOCOLO.md): promoção de
  configurações, bloqueio de teste e ordem experimental.
- [`metodologia/TOLERANCIA_ESPACIAL.md`](metodologia/TOLERANCIA_ESPACIAL.md):
  decisão de 10 px principal e 15/20 px de sensibilidade obrigatória, com
  auditoria descritiva das anotações dos 12 vídeos de treino, sem detector.
- [`metodologia/CLASSES_E_AGRUPAMENTOS.md`](metodologia/CLASSES_E_AGRUPAMENTOS.md):
  indivíduos 0/2, proteção contra duplicatas, regiões de agrupamento
  ignoradas e avaliação complementar de todos os objetos, no protocolo v3.
- [`metodologia/ESTATISTICA_E_PARETO.md`](metodologia/ESTATISTICA_E_PARETO.md):
  agregação por vídeo, testes pareados, IC95 e custo-benefício.
- [`metodologia/METRICAS_TRACKING.md`](metodologia/METRICAS_TRACKING.md):
  contratos, eventos de identidade e avaliação MOT oficial.

## Dados e operação

- [`dados/FORMATO_VISEM.md`](dados/FORMATO_VISEM.md): formatos do VISEM,
  VISEM-Tracking, labels, IDs e política para lacunas.
- [`operacao/AMBIENTE.md`](operacao/AMBIENTE.md): ambientes CPU e CUDA.
- [`../script/README.md`](../script/README.md): comandos oficiais de teste e
  aplicação.

## Algoritmos

As fichas em [`algoritmos/`](algoritmos/README.md) registram separadamente
teoria, parâmetros, pontos fortes, limitações, custo e decisão de promoção de
cada detector, tracker, estimador de fluxo e preditor. Baseline puro e variante
híbrida nunca compartilham a mesma ficha ou configuração.

## Referências

- [`referencias/datasets/`](referencias/datasets/README.md): links oficiais e
  documentos descritivos dos datasets.

Documentos substituídos não permanecem misturados à documentação vigente.
Quando uma remoção definitiva depender de revisão humana, o arquivo é isolado
temporariamente fora de `docs/`.

## Marco atual: linha de base e referência individual

- [Congelamento do threshold v3 para desenvolvimento](metodologia/CONGELAMENTO_THRESHOLD_V3.md).
- [Referência de trajetórias individuais v1](metodologia/TRAJETORIAS_INDIVIDUAIS_V1.md).
- [Baselines de predição com referência individual](metodologia/BASELINES_PREDICAO_V1.md).
