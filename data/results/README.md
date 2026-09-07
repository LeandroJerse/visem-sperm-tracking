# Resultados confirmatórios

Esta pasta recebe apenas:

1. decisão e configuração congelada;
2. execução única no teste isolado;
3. previsões fora da amostra da confirmação 5-fold;
4. aplicação final nos 65 vídeos sem tracking manual.

Validação e tuning ficam em `../tests/`. Uma pasta vazia de `test/`, `oof/` ou
`application/` não deve ser preenchida manualmente: somente o executor cria
runs imutáveis.

`selection/` é a única exceção à terminação em `<run_id>`: não representa uma
execução, e sim o registro versionável que referencia as runs de validação,
justifica a promoção e identifica o YAML congelado. Nenhum CSV de detecção,
vídeo ou métrica bruta é copiado para essa pasta.
