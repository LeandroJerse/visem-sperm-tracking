# Watershed: vídeos completos de seleção

Preparação aprovada em 21/09/2026, após a [seleção em imagens](analise_selecao_watershed.md).
As cinco configurações aprovadas são **s063, s064, s061, s062 e s098**, nesta ordem.
O plano está preparado; **o pesquisador executará os vídeos**.

## O que esta etapa responde

A seleção comparou 114 configurações em 60 JPEGs. Agora aplicaremos as cinco
aprovadas a todos os quadros dos mesmos quatro vídeos, mantendo a detecção e
os critérios. Isso permite observar falhas persistentes, mudanças ao longo
da sequência e a variação entre vídeos. Os quadros consecutivos são
relacionados; esta etapa não é uma avaliação independente nem um teste de
significância. O histórico de uso dos dados permanece registrado.

| Vídeo | Quadros | FPS | Duração |
|---|---:|---:|---:|
| 13 | 1.470 | 49 | 30 s |
| 29 | 1.470 | 49 | 30 s |
| 52 | 1.440 | 48 | 30 s |
| 54 | 1.470 | 49 | 30 s |

Total: **5.850 quadros por configuração, 29.250 avaliações e vinte MP4s
comparativos**. Cada configuração processa os mesmos pixels e anotações,
na resolução original de 640×480. O comparativo tem 1280×584, incluindo os
cabeçalhos, com anotações à esquerda e detecções à direita.

## Configurações congeladas

| ID | Origem | Ajuste de Otsu | Fração de semente | Política de aglomerados |
|---|---|---:|---:|---|
| s063 | round2 / r2c19 | −10 | 0,75 | Separar |
| s064 | round2 / r2c20 | −10 | 0,75 | Preservar por área |
| s061 | round2 / r2c17 | −20 | 0,75 | Separar |
| s062 | round2 / r2c18 | −20 | 0,75 | Preservar por área |
| s098 | round4 / r4c10 | −7 | 0,35 | Preservar por área |

Todas usam objetos claros, conectividade 8, abertura desativada, fechamento
retangular 5×5 com uma iteração e área aceita de 120 a 5.000 pixels.
A classificação usa pequeno até 120 e aglomerado a partir de 900 pixels.
Consequentemente, a previsão de pequeno fica restrita à área exatamente 120.
Essa limitação foi observada na seleção e permanece explícita, sem ajustar
parâmetros após escolher as candidatas.

O [plano JSON](../scripts/watershed/videos/plano_selecao.json) preserva os
parâmetros completos, suas identidades e a linhagem das rodadas. As caixas
continuam envolvendo as regiões segmentadas. Não se introduz margem ou escala.

A localização reúne classes 0 e 2; trocas entre elas são registradas como
erros de classificação separados. Aglomerados têm avaliação própria.
O F1 usa TP, FP e FN somados, com IoU mínimo de 0,50 e correspondência exclusiva.
Empates exatos compartilham posição. O relatório não escolhe uma vencedora
automaticamente. Ausência de anotações e previsões no grupo dá “sem casos”;
somente previsões ou somente anotações dão F1 igual a zero.

## Executar

Na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_videos.py" --etapa selecao
```

Para conferir somente arquivos, versões e metadados:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_videos.py" --etapa selecao --conferir
```

A conferência prévia não decodifica a sequência nem executa o detector. A
verificação temporal ocorre no início da execução completa, antes de detectar:

1. Conferir os hashes das quatro mídias, 5.850 anotações, vinte JPEGs de
   referência, plano, dezenove fontes de seleção e código de origem.
2. Decodificar os vídeos completos, verificar dimensões, FPS e quantidade
   de quadros. Comparar cada uma das cinco referências JPEG por vídeo com
   todos os frames pelo MAE em cinza; o índice previsto deve ser o mínimo único.
3. Registrar o hash de cada frame decodificado. Conferir esses pixels novamente
   em cada configuração, preservando a comparação entre as cinco.
4. Detectar cada quadro, salvar caixas, medidas, pareamentos, erros, diagnóstico
   da segmentação e métricas. Gravar o vídeo comparativo.
5. Reabrir integralmente cada MP4 produzido e conferir quantidade de quadros,
   dimensões e FPS. Somar as métricas e gerar o relatório.
6. Conferir novamente as fontes originais e registrar os hashes das saídas.

Anotação ausente, vídeo truncado, alinhamento ambíguo ou pixels diferentes
interrompem a execução. Arquivo de anotação existente e vazio é válido.
A conferência MAE usa cinco referências por vídeo; não garante identidade
de pixels entre JPEG e MP4, formatos com compressão diferente.

## Organização das saídas

```text
resultados/videos/watershed/selecao/batch__<UTC>/
├── <ID>__<configuracao>__cfg-<hash>__<UTC>/
│   ├── midia/<ID>__cfg-<hash>__video-<numero>.mp4
│   ├── deteccoes.csv, anotacoes.csv, pares.csv, pendentes.csv
│   ├── por_quadro.csv
│   ├── configuracao.json, execucao.json, avaliacao.json
│   └── resumo.csv, resumo_por_video.csv
├── conferencia/
├── origens/
├── relatorios/<UTC>/relatorio.pdf
├── ranking.csv, resumo_configuracoes.csv, resumo_por_video.csv
├── plano.json, execucao.json, relatorio.json
└── codigo.zip
```

`por_quadro.csv` inclui índice, tempo relativo (índice/FPS), limiar Otsu
original/efetivo, pixels da máscara, componentes, sementes, regiões,
rejeições, detecções, tempo do detector e métricas. `deteccoes.csv`
preserva caixas, centroides, área segmentada, perímetro e medidas de forma.
Os índices identificam objetos somente dentro do quadro: não há rastreamento,
velocidade ou contagem de indivíduos únicos.

O tempo medido envolve a mesma chamada de inspeção usada nas imagens,
incluindo segmentação e diagnóstico. Exclui leitura, avaliação, desenho e
gravação do vídeo; não representa o desempenho completo da aplicação.
Mapas e imagens de cada frame não são exportados nesta etapa de vídeo;
os comparativos MP4 e as tabelas preservam as saídas para inspeção.

Cada execução cria uma pasta nova. Uma interrupção conserva os arquivos
parciais, mas a próxima execução começa novamente. Não apagar resultados,
`codigo.zip` ou `origens/`: eles sustentam a reprodução e a auditoria.

## PDF e recuperação

O relatório automático contém quatro páginas:

1. F1 de indivíduos, precisão e recall, com gráfico em escala fixa de 0 a 1.
2. Cobertura de normais, pequenos e aglomerados, erros 0/2 e acurácia condicional.
3. Resultados de cada configuração em cada vídeo.
4. Tempos, parâmetros congelados e limites da interpretação.

O gerador confere plano e origens, código arquivado, métricas dos 29.250
quadros, agregações, ranking, configurações e hashes das vinte mídias.
Ele usa o registro da decodificação feito pelo executor, sem decodificar
novamente os vídeos nem reler todas as tabelas de caixas e pares.

Se apenas o PDF falhar, as métricas e mídias concluídas permanecem válidas.
Para gerar outro relatório:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_videos.py" --somente-relatorio "CAMINHO_COMPLETO_DO_BATCH"
```

## Conferência da preparação e próxima etapa

A conferência real de arquivos, versões e metadados passou, sem detectar
quadros da base. Passaram **90 testes**: 18 específicos do plano, executor
e relatório, mais 72 regressões de vídeo e watershed. Os testes usam vídeos
artificiais, verificam equivalência com a saída em imagens, preservação das
fontes, falhas e integridade. O PDF fictício teve suas quatro páginas
revisadas visualmente. Isso verifica a implementação, não o desempenho real.

O gerador reproduz o plano byte a byte. O arquivo de estatísticas da seleção
mantém o estado anterior à aprovação; a decisão posterior está registrada
neste plano, sem alterar aquela evidência.

Após a execução, conferir integridade, F1, cobertura por classe, erros e
comparativos visuais em conjunto. Só depois preparar os vídeos finais
**14, 24, 38 e 82**, mantendo explícito o histórico de exposição aos dados.

