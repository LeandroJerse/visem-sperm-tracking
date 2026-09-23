# Watershed: seleção nas imagens reservadas

Preparação aprovada em 21/09/2026, após a [análise do round5](analise_round5_watershed.md).
As cinco rodadas estão encerradas. Esta etapa compara o catálogo já testado,
sem acrescentar parâmetros ou executar outra busca. A execução real fica com
o pesquisador. Ele concluiu a seleção em `batch__20260921T203527246803Z`;
a [análise e conferência](analise_selecao_watershed.md) registram os resultados
e as cinco candidatas, posteriormente aprovadas. Os
[vídeos completos de seleção](plano_videos_watershed.md) estão preparados
para execução, sem mudanças nos parâmetros.

## Catálogo e imagens

As rodadas tiveram 48, 32, 24, 18 e 14 configurações: 136 ocorrências,
das quais 22 repetem controles anteriores. A comparação usa as **114
configurações distintas**, incluindo resultados inferiores do desenvolvimento.
São **20 manuais e 94 Otsu**, preservando as duas políticas de aglomerados,
os deslocamentos de Otsu e as polaridades presentes nos planos anteriores.

Os identificadores `s001` a `s114` seguem a primeira aparição no histórico,
não a posição no ranking. Cada item do [plano congelado](../scripts/watershed/selecao/plano.json)
guarda todos os IDs anteriores, parâmetros completos, caminhos e hashes das
configurações de origem. Igualdade exige os mesmos parâmetros completos;
configurações apenas semelhantes não são removidas.

Todas usam os mesmos **60 JPEGs e suas anotações**: vídeos **13, 29, 52 e 54**,
quadros **0, 100, 200, …, 1400**, quinze por vídeo. A composição e os hashes
vêm do plano de seleção da limiarização. Nenhum quadro é extraído novamente
do vídeo; isso evita introduzir diferenças de decodificação nesta comparação.
Não há exclusões. Total: **114 × 60 = 6.840 avaliações**.

Essas imagens já foram usadas na seleção de limiarização e blobs. Portanto,
são reservadas em relação ao ajuste de watershed, mas não são dados inéditos
para a pesquisa. A seleção não é uma avaliação final independente.

## Critérios mantidos

- Ranking por **F1 de localização de indivíduos (0 e 2 juntos)**, somando TP,
  FP e FN dos 60 quadros antes de calcular `2TP/(2TP+FP+FN)`.
- Correspondência exclusiva entre caixas do mesmo grupo, com IoU ≥ 0,50;
  maximiza primeiro o número de pares e depois a soma das IoUs.
- Trocar 0 por 2, ou 2 por 0, conta como localização correta e erro de
  classificação separado. A matriz 0/2 e a acurácia condicional usam apenas
  indivíduos pareados; não incluem objetos perdidos ou falsas detecções.
- Aglomerados (1) continuam em avaliação separada. Trocas entre indivíduo e
  aglomerado geram FN no grupo anotado e FP no previsto.
- Cobertura por classe original e métricas por vídeo complementam o F1.
  Somar indivíduos dá maior influência aos grupos com mais objetos;
  a cobertura de pequenos deve ser examinada explicitamente.
- Sem anotações nem previsões: F1 indefinido, mostrado como `s/c` (sem casos).
  Apenas FP ou FN: F1 zero. Ausência de casos não é transformada em zero.
- O ranking compara frações exatas, sem decidir por arredondamento. Empates
  compartilham posição; ID só organiza a exibição. Não há peso adicional nem
  desempate automático. Se o empate atravessar a quinta vaga, o relatório
  avisa e registra todos os IDs envolvidos para revisão conjunta.

Nenhum arquivo de finalistas é criado automaticamente. Os cinco candidatos
serão revisados com o pesquisador após conferir esta execução.

## Compatibilidade e reprodução

O detector, suas caixas e o avaliador permanecem os mesmos. Configurações
manuais usam o escritor original; Otsu usa a variante já existente, que
retorna ao detector original quando o deslocamento é zero. Não se converte
um limiar manual em Otsu para caber no executor.

Todas as configurações produzem os mesmos doze arquivos por quadro. Para
o método manual, `segmentacao.json` registra `limiar_otsu_original: null`,
deslocamento zero e o limiar manual efetivo. A contagem de pixels é obtida da
máscara já salva. A classificação mantém os limites de área de cada configuração.

Antes da detecção, o executor confere o plano congelado, **274 entradas de
integridade** (plano, 153 origens históricas e 120 arquivos de imagem/anotação),
a decodificação das imagens, as versões das bibliotecas e a compatibilidade
das fontes com o round5. Os mesmos bytes de entrada são usados em todas as
configurações. O arquivo `codigo.zip` guardará **42 fontes** da execução.

As 153 origens incluem os cinco planos, manifestos e arquivos de código,
as 136 configurações históricas, a composição das imagens de seleção e a
análise consolidada do round5. São copiadas para `origens/`. Conserve os
resultados anteriores e seus `codigo.zip`: eles permitem rastrear o catálogo.

As imagens diferem das usadas no desenvolvimento. Assim, não se exige
igualdade das detecções desta seleção com saídas antigas; `controles.json`
registra zero casos históricos comparáveis. A compatibilidade entre os
escritores foi testada com imagens sintéticas, comparando caixas, detecções,
avaliações e diagnósticos byte a byte. Isso verifica implementação, não eficácia.

A lista de parâmetros é fixa e não há sorteio durante a seleção. A seed 42
permanece registrada, mas a reprodução depende também dos planos, entradas,
código e versões. O ambiente conferido usa Python 3.13.3, OpenCV 4.13.0,
NumPy 2.3.3, SciPy 1.16.2 e scikit-image 0.26.0.

## Executar

Na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_selecao.py"
```

O plano já está preparado; não é necessário executar seu gerador. Para
conferir somente as entradas, sem detecção ou pasta de resultados:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_selecao.py" --conferir
```

Cada execução cria uma pasta nova, preservando as anteriores:

```text
resultados/frame-to-frame/watershed/selecao/batch__<UTC>/
  plano.json, execucao.json, codigo.zip, controles.json
  origens/
  ranking.csv, resumo_configuracoes.csv
  resumo_por_quadro.csv, resumo_por_video.csv
  sNNN__<metodo-polaridade-semente-politica-area-fechamento>__cfg-<hash>__<UTC>/
    configuracao.json, avaliacao.json
    quadros/<video>_frame_<quadro>/
  relatorios/<UTC>/relatorio.pdf
  relatorio.json
```

O nome identifica a configuração e o hash distingue o conjunto completo dos
parâmetros. Em Otsu, `dm5` significa deslocamento −5; `dp0`, deslocamento zero.
A pasta de cada quadro contém comparação visual, caixas, máscaras, mapas,
detecções, avaliação, pares, pendentes, diagnóstico e metadados de segmentação.

Uma interrupção conserva os resultados parciais e registra sua situação;
não há retomada automática. Uma nova execução inicia outro batch. Uma falha
exclusiva no PDF preserva as métricas concluídas. Para regenerar somente o PDF:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_selecao.py" --somente-relatorio "CAMINHO_COMPLETO_DO_BATCH"
```

## Relatório e conferências

O PDF automático tem **oito páginas**:

1. Dez primeiras posições, F1, precisão, recall, TP/FP/FN, aglomerados,
   tempo e distribuição descritiva do F1 entre configurações.
2. Três páginas com as 114 posições, parâmetros resumidos e origem histórica.
3. Quatro páginas com cobertura de 0/2/1, trocas 0/2, acurácia condicional,
   F1 em cada um dos quatro vídeos e F1 de aglomerados, para todas as candidatas.

O mapa de cores usa a mesma escala 0–1 em todos os vídeos. Quartis e
diferenças por vídeo são descrições, não testes de significância. Quadros do
mesmo vídeo são correlacionados. O tempo apresentado mede detector e
diagnósticos internos, excluindo leitura, avaliação, gravação e PDF.

O relatório confere planos, origens, código arquivado, contagens, ranking,
agregações por configuração/vídeo e metadados. Não executa novamente o
detector nem relê todas as mídias. A conferência completa dos arquivos da
execução real será feita quando o pesquisador informar sua conclusão.

Preparação: conferência real das entradas aprovada sem detecção; plano
reproduzível; PDF fictício de oito páginas revisado visualmente. A suíte
específica verifica catálogo, preservação das variantes, saídas sintéticas,
interrupções, hashes, casos indefinidos, empates e recuperação do relatório.
Passaram **93 testes** (79 anteriores e 14 da seleção), conforme o
[estado da pesquisa](estado_pesquisa.md). Nenhum experimento real foi
executado nesta preparação; a prévia fictícia foi removida após a revisão.

## Próxima etapa

Após a execução: conferir a integridade, analisar o ranking e a cobertura
por classe/vídeo e revisar cinco finalistas com o pesquisador. Só então
preparar seus testes nos vídeos completos 13, 29, 52 e 54. Após essa revisão,
congelar as escolhas para os vídeos finais 14, 24, 38 e 82, preservando o
histórico de exposição aos dados. A infraestrutura de vídeos não faz parte
desta preparação.

## Arquivos desta preparação

- [Gerador do catálogo](../scripts/watershed/planejamento_selecao.py),
  [plano congelado](../scripts/watershed/selecao/plano.json) e
  [executor](../scripts/watershed/executar_selecao.py).
- [Compatibilidade das saídas](../scripts/watershed/saidas_selecao.py),
  [relatório](relatorio_selecao_watershed.py) e
  [testes](../scripts/testes/test_selecao_watershed.py).
- O executor comum passou a registrar a etapa do plano; o leitor de
  relatórios aceita a quantidade de quadros e a etapa da seleção, mantendo
  os valores padrão das rodadas. Guias e estado da pesquisa foram atualizados.

Os módulos do detector e do avaliador não foram alterados nesta etapa.
