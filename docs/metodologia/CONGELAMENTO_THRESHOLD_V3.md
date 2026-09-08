# Congelamento do threshold v3 para desenvolvimento

Decisão de 08/09/2026: fixar **T218/o0/c2** como linha de base de desenvolvimento,
após a [validação completa](VALIDACAO_THRESHOLD_V3.md). O arquivo executável é
[t218_o0_c2_v3.yaml](../../configs/frozen/detection/threshold/t218_o0_c2_v3.yaml).
O resultado permanece de seleção em validação; não é confirmação independente.

## Base da decisão

O congelamento materializa o primeiro colocado pelo critério já registrado:
F1 macro por vídeo dos indivíduos a 10 px, seguido dos desempates registrados.
As duas finalistas completaram os quatro vídeos, com cobertura integral e
conferência independente aprovada. Não foi criado um corte de qualidade após
observar os resultados e não houve busca adicional. O F1 macro de T218 foi
0,658959, contra 0,657819 de T219; cada uma venceu em dois vídeos.

Antes de criar o novo YAML, foram reconferidos os hashes dos **46 artefatos
exportados** utilizados na conferência, a seleção, o plano de validação e seus
pais. O recibo local é
`data/derived/project_audits/general_20260908/freeze_t218_development_20260908.json`.
Esse recibo registra uma decisão derivada de resultados existentes; não é uma
nova execução experimental. Nenhum vídeo ou arquivo original de anotação foi
aberto nessa materialização.

O detector, suas estruturas de dados, registro, executor, I/O, leitura estrita,
avaliador e conferência de métricas por quadro foram comparados com `7f47afb`:
conteúdo igual após normalizar apenas finais de linha CRLF. Seus hashes locais
exatos constam do recibo. As novas guardas de liberação mudam a orquestração;
não reatribuem as métricas antigas ao código novo. A proveniência da validação
continua em `7f47afb`, com o hash original de fonte registrado no YAML.

## O que ficou fixo

| Parte | Valor |
|---|---|
| Limiar | 218, binarização fixa sem inversão |
| Suavização | `blur=1` |
| Morfologia | kernel 3; abertura 0; fechamento 2 |
| Área | mínimo 3; máximo 300 |
| Avaliação | `center_distance_v3_individuals_ignore_clusters_10px` |
| Sensibilidades | 15 e 20 px |
| Universo principal | indivíduos 0/2, regra v3 para predições residuais em agrupamentos |

As regras completas continuam em [classes e agrupamentos](CLASSES_E_AGRUPAMENTOS.md).
O YAML histórico T200/o1/c2 a 15 px permanece intacto e não é convertido para v3.

## Limite de uso executável

O bloco `freeze.scope=development_only` permite somente `development/train`,
`smoke/train` e `validation/val`. Os executores conferem o escopo no arquivo
original antes de ler entradas; a flag `frozen` precisa permanecer verdadeira,
e o caminho e o hash dos splits registrados precisam coincidir. Alterações de
parâmetros científicos continuam vedadas pelas guardas de configuração.

Teste, folds, `all` e aplicação não são liberados por esse congelamento.
`confirmatory_plan: null` explicita que ainda não existe desenho confirmatório
aprovado para esta configuração. Requerer outro desenho e outra configuração
no futuro evita reescrever esta decisão para simular uma autorização anterior.
O teste já foi exposto historicamente; o bloqueio atual não restaura cegueira.

## Continuidade

A etapa seguinte prepara a [referência de trajetórias individuais no treino](TRAJETORIAS_INDIVIDUAIS_V1.md).
Ela preserva IDs originais e segmentos, sem executar rastreador ou preditor.
O contrato de HOTA, o consumo causal de fluxo e a comparação pareada por vídeo
com/sem fluxo continuam marcos próprios, ainda sem resultados confirmatórios.
