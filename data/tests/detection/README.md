# Desenvolvimento de detecção

[Mapa dos dados](../../README.md) · [Algoritmos](../../../src/detection/README.md)
· [Bancada frame a frame](../../../script/detection/test/threshold/README.md)

## Caminhos dos artefatos locais

As runs não acompanham o código versionado. Os caminhos abaixo são relativos
a `data/tests/detection/` e descrevem as saídas locais.

- Threshold fixo (`threshold/`) e Otsu (`otsu/`): configurações e triagens
  organizadas separadamente.
- Comparações do frame a frame (`threshold/_comparisons/frame_screening/`):
  tabelas históricas e agregações disponíveis.
- Imagens de entrada compartilhadas (`_shared_inputs/`): frames usados nos
  diagnósticos, sem duplicação por configuração.
- MOG2 (`mog2/`), Blob (`blob/`), Watershed (`watershed/`) e YOLO (`yolo/`):
  diretórios existentes; presença de pasta não comprova avaliação concluída.

Consulte a [matriz científica](../../../docs/projeto/MATRIZ_EXPERIMENTOS.md)
para distinguir piloto, validação e etapas pendentes. As pastas de outros
detectores são criadas quando suas execuções produzem artefatos.

## Como ler uma run

Cada algoritmo possui sua pasta e, dentro dela, uma configuração legível com
hash, uma etapa e uma run imutável. `_shared_inputs/` evita duplicar as 60
imagens dos testes frame a frame; `_comparisons/` agrega configurações sem
alterar as runs originais.

Conteúdo `legacy` ou `pilot` é histórico. Validação oficial também permanece
nesta árvore porque ainda participa da escolha da configuração.

A triagem nova usa somente treino por padrão, recusa IDs do teste antes de
decodificar o vídeo e não grava métricas para lacunas sem label. Runs novas de
frame screening seguem diretamente
`<algoritmo>/<configuração>/frame_screening/<run_id>/`; vídeo e frame são
atributos do manifesto, não níveis extras de pasta.

MOG2/KNN usam uma unidade diferente: as runs de triagem continuam sob a mesma
hierarquia canônica, mas cada uma registra `clip_windows.csv`. As comparações
macro por vídeo ficam em
`<mog2|knn>/_comparisons/clip_screening/`; o aquecimento nunca entra nas
métricas.
