# Estado da pesquisa e continuidade

Atualizado em 21/09/2026. Síntese das decisões vigentes, resultados e próximo
trabalho. Os documentos vinculados preservam os detalhes e as justificativas.

## Ponto de retomada

**Blobs concluído; watershed com vídeos de seleção preparados para execução.**

- Aprovadas **s063, s064, s061, s062 e s098**, mantendo os parâmetros da
  seleção em imagens. [Plano e comandos](plano_videos_watershed.md).
- Próximo comando: `scripts/watershed/executar_videos.py --etapa selecao`.
  Execução pelo pesquisador: 5.850 quadros por configuração, 29.250
  avaliações, vinte MP4s e PDF de quatro páginas. Saída em
  `resultados/videos/watershed/selecao/batch__<UTC>/`.
- Conferidos arquivos reais e metadados: quatro MP4s, 5.850 anotações,
  vinte JPEGs de alinhamento e dezenove fontes da seleção. Código anterior
  e dependências preservados. Nenhum detector executado na base.
- Passaram 90 testes: 18 específicos e 72 regressões; vídeos artificiais,
  equivalência de caixas com imagens, interrupções, métricas e integridade.
  Plano reproduzido byte a byte e quatro páginas do PDF fictício revisadas.
- Alinhamento MAE e identidade de pixels serão verificados na execução.
  Após a revisão dos resultados, preparar os vídeos finais 14, 24, 38 e 82.
  Não há plano final preparado ou resultados reais de vídeo nesta etapa.

### Seleção em imagens concluída

- Batch `batch__20260921T203527246803Z`: 114 configurações × 60 imagens,
  6.840 avaliações e PDF de oito páginas. Conferidos 82.468 hashes de saídas
  (7.285.764.581 bytes), 274 entradas/origens e 42 fontes de código.
- Avaliações, pares, pendentes, candidatos e agregações reconciliados em
  todos os 6.840 casos. Pareamentos recalculados das caixas nas 60 imagens
  de cada uma das seis primeiras: **360 avaliações idênticas**.
  PDF e 7.228 fontes conferidos; oito páginas revisadas visualmente.
- Ranking aprovado para os vídeos: **s063, s064, s061, s062 e s098**. F1 respectivamente
  0,342956; 0,341078; 0,315674; 0,302003; 0,291024. Sem empate na quinta vaga.
  O plano de vídeos registra a aprovação posterior à auditoria original.
- s063: 398 TP, 663 FP, 862 FN; 396/1.200 normais, 2/60 pequenos e 28/45
  aglomerados localizados. As cinco propostas não acertaram a classe de
  nenhum pequeno localizado. A área aceita começa em 120 e classe 2 vai
  até 120, restringindo essa previsão a regiões com exatamente 120 pixels.
- Das 862 perdas de s063, 827 têm candidatos sobrepostos, mas com IoU
  insuficiente. Em 687 desses casos a melhor caixa candidata é menor que
  a anotada. Só seis FN têm candidato rejeitado pelo mínimo com IoU suficiente.
  Trocar apenas classes ou baixar apenas o mínimo não resolve o diagnóstico.
- r5c10 corresponde a s110: F1 0,250587, 22º lugar na seleção.
  A liderança muda ao retirar vídeos 52 ou 54; análise descritiva, sem
  validação cruzada ou novo critério. Todos os quadros têm 640×480 pixels.
- [Análise completa](analise_selecao_watershed.md) e
  [estatísticas](estatisticas_selecao_watershed.json) preservam evidências.
  A preparação dos vídeos completos 13, 29, 52 e 54 foi aprovada e concluída.
  Final nos vídeos 14, 24, 38 e 82 permanece posterior. O JSON de estatísticas
  preserva o estado anterior à aprovação, sem reescrever a evidência histórica.

### Registro da preparação da seleção de watershed

- Preparação aprovada após a análise do round5: **114 configurações distintas
  × 60 imagens = 6.840 avaliações** nos vídeos 13, 29, 52 e 54, quadros
  0, 100, …, 1400. São 20 manuais e 94 Otsu, preservando 136 origens
  históricas, parâmetros e critérios. Não há novos ajustes.
- [Plano e comandos](plano_selecao_watershed.md),
  [JSON congelado](../scripts/watershed/selecao/plano.json) e
  [executor](../scripts/watershed/executar_selecao.py) preparados.
  Esse comando reproduz a seleção já concluída; não precisa ser repetido.
- Conferência real sem detecção passou: 274 entradas de integridade,
  60 imagens válidas e 42 fontes de código a arquivar. Saídas do método
  manual e de Otsu são compatibilizadas sem mudar detector ou avaliador.
- PDF automático de oito páginas: ranking completo, cobertura 0/2/1,
  classificação e F1 por vídeo; prévia fictícia revisada visualmente.
  Empates exatos na quinta vaga são sinalizados, sem promoção automática.
- Passaram **93 testes sintéticos e de regressão**: 79 anteriores e 14
  específicos da seleção, incluindo compatibilidade manual/Otsu, repetição,
  interrupções, integridade, empates, casos indefinidos e recuperação do PDF.
  O plano foi reproduzido byte a byte; 42 fontes e os links locais foram
  conferidos. Nenhuma seleção real foi executada nesta preparação.
  A prévia fictícia foi removida após a revisão. A edição preexistente de
  `scripts/configuracoes/limiarizacao.modelo.json` permaneceu intacta.
- Após o pesquisador executar, conferir arquivos e métricas e revisar
  cinco finalistas em conjunto. Somente depois preparar os vídeos completos
  de seleção; a avaliação final continua sendo uma etapa posterior.

### Análise concluída do round5

- Round5: `batch__20260921T193215730860Z`, 14×178 = 2.492 avaliações.
  Conferidos 34.218 hashes de saídas, 4.636 origens, 38 fontes e 1.068
  controles idênticos ao round4. Tabelas, avaliações, pares e pendentes
  reconciliados; pareamentos dos 178 quadros da líder recalculados das caixas.
  PDF original de cinco páginas e 11.078 fontes conferidos, com inspeção visual.
- Líder r5c10: **F1 0,482362**, ante 0,481308 de r4c16/r5c02.
  São 1.887 TP, 2.339 FP e 1.711 FN: +33 TP e +87 FP.
  Otsu −5, semente 0,50, mínimo 120, fechamento 3 e preservação por área.
  Normais: 1.881/3.464; pequenos: 6/134, antes 10/134, todos previstos como 0.
- Melhora sete vídeos e piora cinco. Ao retirar um vídeo por vez entre
  as 114 configurações distintas, r5c10 lidera quatro vezes, r5c12 quatro,
  r4c16 três e r5c13 uma. É análise de sensibilidade, não validação cruzada.
- [Análise do round5](analise_round5_watershed.md) e
  [estatísticas completas](estatisticas_round5_watershed.json) encerram o
  diagnóstico do desenvolvimento. Dos 1.711 FN da líder, 1.591 apresentam
  IoU insuficiente. Nenhuma configuração do round5 acertou a classe 2
  de um pequeno localizado.
- Os cinco rounds foram encerrados, sem round6. A preparação da seleção
  proposta nesta análise foi aprovada e concluída, conforme o ponto de
  retomada acima. As cinco finalistas ainda não foram escolhidas.

### Registro da preparação do round5

- [Plano aprovado e congelado](plano_round5_watershed.md): 14 configurações,
  seis controles e oito combinações novas, nos mesmos 178 quadros.
  São 2.492 avaliações previstas e 114 configurações distintas nos cinco
  planos, incluindo as oito novas ainda não executadas.
- Combina Otsu −3/−5, semente 0,50 e fechamento 3/5; acrescenta um par de
  área mínima 144. Mantém controles com semente 0,35. Cada um dos 14 contrastes
  altera somente um parâmetro, inclusive as referências da combinação tripla.
- Conferência sem detecção passou: 4.636 origens íntegras, 1.068 casos de
  controle disponíveis e 38 fontes de código a arquivar. Detector, caixas,
  escritor de saídas e critérios preservados.
- Mesmo executor: `scripts/watershed/executar_rodada.py --rodada round5`.
  PDF automático de cinco páginas; a última apresenta os contrastes.
  As cinco páginas da prévia fictícia foram conferidas visualmente.
- Passaram 79 testes sintéticos (67 anteriores e 12 novos), incluindo os
  contrastes da combinação tripla, reprodução, falhas e recuperação do PDF.
  O plano foi reproduzido byte a byte e sua matriz conferida com a proposta.
- Após a execução do pesquisador, conferir controles, integridade, diferenças
  por vídeo e limitações; então preparar a seleção em outras imagens.
  Nenhuma rodada real ou seleção foi executada durante esta preparação.
  O pesquisador executou a rodada depois; a conferência está registrada acima.

### Análise concluída do round4

- Batch `batch__20260921T184319705365Z`: 18×178 = 3.204 avaliações completas.
  Conferidos 42.769 hashes de saídas, 4.635 origens, 35 fontes de código
  e 1.068 controles idênticos ao round3. Tabelas, avaliações, pares e metadados
  reconciliados. Pareamentos dos 178 quadros da líder recalculados das caixas
  salvas e idênticos. PDF de cinco páginas e 11.797 fontes conferidos.
- Líder r4c16: F1 **0,481308**, ante 0,478007 no round3. São 1.854 TP,
  2.252 FP e 1.744 FN: +12 TP e −15 FP. Otsu −5, semente 0,50, área 120,
  fechamento 5 e preservação por área. Pequenos: 10/134, todos previstos como 0.
- Melhora em seis vídeos, piora em cinco e empata em um. Ao retirar um
  vídeo por vez, r4c16 lidera seis vezes, r4c08 quatro, r4c15 uma e r4c18 uma,
  entre as 18 configurações. Distância entre as primeiras: 0,000794.
- Semente 0,50, Otsu −3 e fechamento 3 melhoram seus contrastes nas duas
  políticas. Otsu −7 piora. Área 144 elimina FP com perda de cobertura.
  Das 1.744 perdas individuais da líder, 1.625 têm IoU insuficiente.
- [Análise e proposta](analise_round4_watershed.md) e
  [estatísticas](estatisticas_round4_watershed.json) preservam as evidências.
  A proposta de round5 com 14 configurações (seis controles e oito novas)
  foi aprovada e preparada, conforme o ponto de retomada acima.

### Registro da preparação do round4

- [Plano do round4](plano_round4_watershed.md) aprovado e congelado: 18
  configurações, seis controles e 12 novas, nos mesmos 178 quadros.
  São 3.204 avaliações previstas. Otsu −3/−7, áreas 132/144, semente 0,50
  e fechamento 3×3 são contrastados com −5/área 120/semente 0,35/fechamento 5.
  Cada contraste altera um parâmetro; as duas políticas permanecem em pares.
- Conferência sem detecção passou: 4.635 origens íntegras e 1.068 casos
  de controle disponíveis. O código a arquivar tem 35 fontes.
- Mesmo detector, escritor de saídas, métricas e estrutura de pastas.
  PDF automático de cinco páginas; a última compara os 12 refinamentos.
- Passaram 67 testes sintéticos (56 anteriores e 11 novos). As cinco
  páginas da prévia fictícia do PDF foram conferidas visualmente; as 18
  configurações coincidem com a proposta aprovada. Os quatro planos somam
  106 configurações distintas, incluindo as 12 novas ainda não executadas.
- O pesquisador executou a rodada após essa preparação. A conferência está
  registrada acima; o comando permanece disponível para reprodução.

### Registro da análise do round3

- Batch `batch__20260921T174126692210Z`: 24×178 = 4.272 avaliações completas.
  Conferidos 55.596 hashes de saídas, 4.634 de origens, 32 fontes de código
  e 1.068 controles idênticos ao round2. Todas as avaliações, pares, tabelas
  e metadados reconciliados. Os pareamentos dos 178 quadros da líder foram
  recalculados das caixas salvas e coincidiram. PDF de cinco páginas conferido.
- Líder r3c18: F1 **0,478007**, ante 0,466361 no round2. São 1.842 TP,
  2.267 FP e 1.756 FN: +64 TP e +18 FP. Ajuste Otsu −5, área mínima 120,
  semente 0,35, fechamento 5 e preservação por área.
- Melhora em sete vídeos e piora em cinco; 11 e 22 têm as maiores quedas.
  A líder permanece primeira nas doze retiradas de um vídeo, considerando
  as 24 configurações do round3. Diagnóstico descritivo, não significância.
- Pequenos: 7/134 localizados pela líder, todos previstos como normal.
  Das 1.756 perdas individuais, 1.633 têm candidatos com IoU insuficiente.
  A geometria e a cobertura continuam limitações; mudar somente a classe
  0/2 não recuperaria esses objetos.
- [Análise e proposta](analise_round3_watershed.md) e
  [estatísticas](estatisticas_round3_watershed.json) preservam os resultados.
  A proposta de round4 com 18 configurações (seis controles e 12 novas)
  foi posteriormente aprovada e preparada conforme o registro acima.

### Registro da preparação do round3

- [Plano do round3](plano_round3_watershed.md): 24 configurações, seis controles
  e 18 novas. Áreas 108/132, semente 0,60 e ajustes Otsu -5/+5, em pares
  das duas políticas. Controles de área 120 com sementes 0,35/0,50/0,75.
- Mantidos detector, métricas, 178 quadros e saídas por configuração.
  Conferência sem detecção passou: 4.634 origens íntegras, 1.068 casos
  de referência disponíveis; 32 fontes previstas no arquivo de código.
- PDF automático de cinco páginas, com F1 em seis casas decimais e 18
  contrastes de uma variável contra seus controles. Nenhum experimento
  real do round3 foi executado nesta preparação.
- Passaram 56 testes sintéticos (45 anteriores e 11 novos); as cinco páginas
  da prévia fictícia do PDF foram conferidas visualmente. Conferências de
  entrada e leitura dos resultados históricos do round1 e round2 preservadas.
- O pesquisador executou a rodada após essa preparação. A análise está
  registrada acima; o comando permanece disponível para reprodução.

### Registro da análise do round2

- Batch round2 `batch__20260921T161513364669Z`: 32×178 = 5.696 avaliações.
  Conferidos 71.275 hashes de saídas, 3.209 de origens e 712 controles
  idênticos ao round1. Código: 29 fontes arquivadas iguais às atuais.
  Todas as avaliações e agregações reconciliam; os 178 pareamentos da líder
  foram recalculados das caixas salvas e coincidiram. PDF de cinco páginas
  conferido visualmente, com hashes íntegros.
- Líder r2c10: F1 0,466361; 1.778 TP, 2.249 FP e 1.820 FN.
  Frente a r1c11: menos 1.056 FP e 112 TP; melhora em 11 dos 12 vídeos.
  Otsu sem ajuste, área mínima 120, semente 0,35, fechamento 5 e preservação.
- Refinar área acima de 120 não trouxe ganho agregado com mínimo 144.
  Deslocamentos -20/-10/+10/+20 e fechamentos 3/7 perderam para suas
  referências no agregado. Porém -10 melhora sete vídeos e piora cinco:
  ajustes menores próximos de zero ainda podem ser uma hipótese controlada.
- Primeira e segunda posições diferem só 0,000643; retirar um vídeo muda
  a líder em seis das doze retiradas. Resultado descritivo, sem teste de
  significância ou seleção de finalistas.
- Pequenos: apenas 7/134 localizados pela líder, todos classificados como 0.
  A acurácia condicional de 99,49% não implica boa classificação de pequenos.
  Dos 1.820 FN individuais, 1.650 não têm candidato com IoU suficiente.
- [Análise completa](analise_round2_watershed.md) e
  [estatísticas](estatisticas_round2_watershed.json) registram as evidências.
  A recomendação de refinar o round3 foi posteriormente aprovada e preparada
  conforme o registro acima. Nenhuma configuração nova foi executada na análise.

### Registro do round1 e da preparação do round2

- Batch round1 `batch__20260921T143759308685Z`: 48×178 = 8.544 avaliações.
  Conferidos 94.187 hashes de saídas, 457 origens, 24 controles, 24 arquivos
  de código e quatro páginas do PDF. As tabelas reconciliam com as avaliações;
  os 178 pareamentos da líder foram recalculados a partir das caixas salvas.
- Líder r1c11: F1 0,429887; 1.890 TP, 3.305 FP e 1.708 FN. Comparada com
  r1c03, só o mínimo de área muda de 3 para 72: menos 5.258 FP e 14 TP,
  com melhora de F1 nos 12 vídeos. Pequenos: apenas 6/134 localizados.
- r1c12 fica a 0,000445 de F1 da líder; a vantagem muda sem o vídeo 35.
  Preservar e separar continuam como pares. A máscara é a limitação central:
  1.612 FN não têm candidato com IoU suficiente; caixas pequenas e grandes
  coexistem, portanto não se propõe expansão uniforme nesta rodada.
- [Análise completa](analise_round1_watershed.md) e
  [estatísticas](estatisticas_round1_watershed.json) preservam as evidências.
- [Round2 aprovado e preparado](proposta_round2_watershed.md): 32 configurações, quatro
  controles e 28 novas. Refinar mínimos 96/120/144, sementes, fechamento e
  acrescentar Otsu com deslocamentos −20/−10/+10/+20. São 16 pares de políticas.
  A proposta JSON original permanece intacta; o plano executável está em
  `scripts/watershed/rodadas/round2.json`, congelado com hashes e referências.
  Variante separada `variantes_watershed.py`; deslocamento zero delega ao
  detector histórico. `segmentacao.json` registra limiares e pixels por quadro.
- Conferência sem detecção passou: 178 imagens, 3.209 origens íntegras;
  712 casos de controle disponíveis. PDF automático de cinco páginas.
- Passaram 45 testes sintéticos (28 anteriores e 17 novos); cinco páginas
  da prévia fictícia do PDF conferidas visualmente. Leitura das 8.544 linhas
  e 24 controles do round1 preservada; 29 fontes previstas no arquivo de código.
- O pesquisador executou o round2 após essa preparação; a conferência e os
  resultados estão registrados acima. Não houve experimento real durante
  a preparação ou a análise dos artefatos salvos.

### Registro das etapas anteriores de watershed

- Batch watershed `batch__20260921T135941123246Z`: 48 avaliações, 551 hashes de
  saídas e 16 origens íntegros; PDF de duas páginas conferido. Auditoria dos
  mapas confirmou 2.069 regiões candidatas e 1.659 detecções, com caixas,
  áreas, centroides, TXT normalizado e avaliações consistentes.
- Maior F1 inicial: w04, 0,299639 (83 TP, 304 FP, 84 FN). Nenhum dos sete
  pequenos foi localizado. Preservar aglomerados localizou 4/5. Polaridade
  escura com o Otsu atual selecionou majoritariamente fundo e não teve TP.
- `codigo.zip` foi removido pelo pesquisador durante a conferência e
  restaurado com autorização, com hash idêntico ao original. Demais resultados
  e manifesto preservados.
- [Plano do round1](plano_round1_watershed.md): 48 configurações congeladas
  nos 178 quadros. Composição aprovada: quatro
  referências claras, 36 explorações claras e oito escuras, mantendo pares
  das duas políticas. Seed 42; 24 pares, 8.544 avaliações previstas.
- Executor `scripts/watershed/executar_rodada.py --rodada round1` preparado,
  com controles idênticos ao round0, salvamento de todas as imagens/mapas,
  resumos por configuração/quadro/vídeo, ranking com empates exatos e PDF
  automático de quatro páginas. Recuperação do PDF disponível sem detecção.
- Preparação: 28 testes passaram; 457 origens conferidas; quatro páginas do
  PDF inspecionadas com dados sintéticos. Nenhum detector rodou nos dados
  reais naquela preparação. O round1 foi depois executado pelo pesquisador
  e conferido conforme o ponto de retomada acima. Não é necessário repetir round0.

### Registro da preparação do watershed

- Batch final de blobs: `batch__20260921T034832637647Z`. 29.550 avaliações,
  vinte MP4, 149 hashes de saídas e 5.978 de origens íntegros; PDF de quatro
  páginas conferido. Maior F1 final: s103/DoG, 0,656233, com 75.864 trocas
  normal→pequeno entre 95.453 indivíduos localizados e nenhum pequeno localizado.
- [Conclusão de blobs](conclusao_blobs.md): resultados e comparação descritiva
  com limiarização, preservando limitações e histórico de exposição aos dados.
- [Watershed implementado](plano_watershed.md), com caixas de pixels segmentados,
  sementes por fração da distância máxima de cada componente e duas políticas
  aprovadas: separar ou preservar componentes classificados como aglomerados
  pela área, sem emitir pai e filhos juntos.
- Round0: oito configurações × seis imagens de desenvolvimento, mesmas da
  inspeção de blobs. Testes sintéticos de geometria, métricas, executor e PDF
  passaram; a conferência das 16 origens passou sem rodar o detector real.
- O pesquisador executa `scripts/watershed/executar_inspecao.py`; o
  [guia](../scripts/watershed/README.md) descreve saídas e recuperação do PDF.
  O round1 será preparado após o diagnóstico real. Nenhuma rodada futura foi
  executada ou congelada nesta preparação.

### Histórico de blobs

**Cinco rodadas de blobs concluídas, analisadas e documentadas.**
Ver [análise do round5](analise_round5_blobs.md),
[estatísticas com 41 contrastes](estatisticas_round5_blobs.json) e
[documento completo de desenvolvimento](desenvolvimento_blobs.html).

- Batch final de desenvolvimento: `batch__20260921T001209933359Z`.
  14×178=2.492 avaliações, 17.532 hashes de saídas e 363 origens íntegros.
  Quatro controles reproduziram 712 avaliações; PDF de quatro páginas válido.
- Maior F1: **r5c06, 0,568779**, ante 0,567571 no controle r5c04.
  81 FP a menos, 26 TP a menos; ΔF1 +0,001208 e intervalo exploratório
  [−0,007846; +0,011547]. Sete vídeos melhores e cinco piores.
- DoG mantém r5c10/r4c07/r3c24 como melhor referência: F1 0,544980.
- LoG r5c14: F1 0,442669, ante 0,428430. Mesmos 7.959 candidatos;
  317 classes 1→0, com 149 novos TP normais e 168 FP transferidos para
  indivíduos. 130 ganhos vieram do vídeo 35. Nenhum TP anterior perdido;
  os 14 aglomerados pareados permaneceram, FP desse grupo caíram 470→153.
- Pequenos permanecem limitados: melhores SBD/DoG/LoG localizam 3/0/5 de 134.
- Total das cinco rodadas completas: 136 posições de configuração, 24.208
  avaliações e **119 configurações distintas**: 84 SBD, 22 DoG e 13 LoG.

O documento HTML explica a representação, critérios, hipóteses de cada rodada,
resultados que motivaram a seguinte, gráficos, exemplos reais e catálogo das
119 configurações. A entrega específica solicitada após o round5 está concluída.
O relatório futuro de todo o projeto permanece separado desta síntese de blobs.

**Seleção em imagens concluída e auditada; cinco configurações aprovadas.**
O batch `batch__20260921T011058635016Z` completou 7.140 avaliações, com
51.158 hashes de saídas e 134 de entradas/origens íntegros. PDF de sete páginas
conferido. A [análise da seleção](analise_selecao_blobs.md) fundamentou a aprovação, pelo F1 de
indivíduos: **s052 (0,669617), s082 (0,664032), s084 (0,662461), s103
(0,660178) e s051 (0,635693)**. Não há empate na quinta vaga.
As cinco localizaram 2–7/60 pequenos e 0/45 aglomerados. s103 teve 571
trocas de normal para pequeno; s082/s084 têm os mesmos 840 pares acertados.
Essas limitações acompanham a aprovação conjunta, sem alterar o critério.

O [plano desta etapa](plano_selecao_blobs.md) congela todas as 119 configurações
distintas e os mesmos 60 JPEGs dos vídeos 13, 29, 52 e 54 já previstos no
protocolo: frames 0, 100, …, 1400. São 7.140 avaliações, com F1 de indivíduos
e empates exatos; cobertura e classificação são relatadas separadamente.
O registro anterior de composição pendente foi reconciliado com a seção 4
do plano de blobs e com a autorização para preparar esta comparação.
O comando abaixo reproduz a seleção concluída; não é necessário repeti-la agora.

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_selecao.py"
```

O script gera tabelas, ranking, comparações e PDF. `--conferir` valida entradas
sem detectar; `--somente-relatorio BATCH` gera outro PDF sem repetir o teste.
Preparação conferida: 88 testes passaram; plano e 60 entradas conferidos sem
detecção; PDF sintético de sete páginas renderizado e revisado. Hash do plano:
`b33cdd0b1bb16386230bdf4f55a11bf94b57436ceeabe4c163f4aece885636a4`.
**Vídeos completos de seleção concluídos e auditados.** O batch
`batch__20260921T022547636341Z` completou 29.250 avaliações e vinte MP4s,
com tabelas e PDF. Os 129 hashes de saídas originais e 5.897 de entradas/origens
foram conferidos. A [análise](analise_videos_selecao_blobs.md) registra a mesma
ordem da seleção em imagens: s052 (0,668702), s082 (0,660699), s084 (0,660666),
s103 (0,654109) e s051 (0,636091). Pequenos e aglomerados permanecem limitados.
O comando abaixo apenas reproduz essa etapa; não é necessário repeti-la:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_videos.py" --etapa selecao
```

O alinhamento foi conferido na execução, antes da detecção. Saídas em
`resultados/videos/blobs/selecao/batch__<execucao>/`, com configurações dentro
do batch. A avaliação final das mesmas cinco nos vídeos 14, 24, 38 e 82
foi executada e conferida. Ver o [plano final](plano_videos_final_blobs.md)
e a [conclusão](conclusao_blobs.md). O comando abaixo serve para reprodução.
São **29.550 avaliações e vinte MP4s**, tabelas e PDF, em
`resultados/videos/blobs/final/`, com as 43 cópias de procedência em `origens/`.
Comando de reprodução:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_videos.py" --etapa final
```

O alinhamento dos vídeos finais foi conferido antes da primeira detecção.
As configurações, caixas e métricas permanecem congeladas. Não executar o
experimento nem ajustar parâmetros automaticamente.

Na preparação, a conferência `--etapa final --conferir` validou
43 origens, 5.910 anotações, vinte referências e quatro MP4s, sem detecção.
A execução real posterior foi concluída e auditada conforme registrado acima.
Os doze arquivos de algoritmos/métricas permanecem iguais aos arquivados
na seleção. Plano final SHA256:
`6a379cd2557906336ef2558aa472c207fb897f37dbec9101699e22f38ae218b7`.
Passaram 58 testes (14 do plano final, 22 do executor e 22 do relatório).
PDF final sintético de quatro páginas renderizado e conferido; nenhum
resultado ou PDF histórico foi alterado.

A organização foi corrigida: 22 cópias de procedência em `origens/` e sete
arquivos na raiz do batch. O manifesto anterior e o mapeamento ficam em
`origens/historico_organizacao/`; mídias, tabelas e PDF preservam seus hashes.
Passaram 46 testes e a conferência posterior dos 131 hashes atuais e das
62 fontes do PDF histórico. Detalhes na análise dos vídeos vinculada acima.

Preparação conferida: 96 testes passaram, PDF sintético de quatro páginas
revisado e `--conferir` do plano real aprovado, sem criar resultados ou
processar frames reais. Plano SHA256:
`cc36923b5a846023e8ee538ea25a8e1ce09791a7ee5f798310165749b512b8ed`.

## Registro da preparação do round5

**Round5 preparado, aguardando execução pelo pesquisador.**
O [plano e as justificativas](plano_round5_blobs.md) registram 14 configurações
nos mesmos 178 quadros: quatro controles e dez novas, totalizando 119 distintas
nos cinco planos. São 2.492 avaliações previstas. Não executar automaticamente.

- SBD: área mínima 56/64/72 × margem 2/3; controles r4c03 e r4c04.
- DoG: resposta 0,10/0,12/0,14 × margem 5/6; controle r4c07.
- LoG: resposta 0,12/margem 6; controle r4c18 e uma variante com limite
  de aglomerado equivalente a diâmetro 28, ante 24. Mesma geometria e
  regras de avaliação; o efeito da mudança entre grupos será medido.
- Mesmo executor, plano v5 e PDF de quatro páginas, com seis pares de
  margem e um par de classificação. Seed 42, sem sorteio em execução.

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round5
```

Acrescentar `--conferir` valida entradas e dependências sem detectar.
Depois da execução: conferir integridade e controles, analisar os resultados
e produzir o documento completo de blobs antes da seleção e dos vídeos.
Nenhum resultado do round5 está disponível durante sua preparação.
Passaram 137 testes distintos, a conferência real com `--conferir` e a
reprodução idêntica do plano em Python 3.13.3. O PDF de quatro páginas foi
revisado com dados sintéticos; os quatro planos anteriores foram preservados.

## Registro do round4 e indicação do último refinamento

**Round4 concluído e analisado.**
Ver [análise do round4](analise_round4_blobs.md) e
[estatísticas com 42 contrastes](estatisticas_round4_blobs.json).

- Batch: `batch__20260920T232838676095Z`; 18×178=3.204 avaliações completas.
  22.535 hashes de saídas e362 origens íntegros,24 arquivos de código,
  cinco planos de origem e PDF de quatro páginas conferidos.
- Cinco controles reproduziram890 avaliações,34.635 detecções e4.450 arquivos.
  Candidatos idênticos nos178 quadros dos nove pares de margem.
- **Maior F1 permanece0,567571**, SBD r4c04, repetindo r3c09. Os melhores
  DoG e LoG também são controles, com0,544980 e0,428430.
- Melhor nova: SBD r4c05, área80/margem2, F1 0,566181. Retira139 FP,
  perde62 TP. ΔF1 contra a referência−0,001391, intervalo exploratório
  [−0,039690;+0,041472], cinco vídeos melhores e sete piores.
- DoG: aumentar resposta além da referência derrubou recall; margem8
  piorou os quatro limiares. No vídeo35, resposta0,12→0,16 reduziu TP189→2.
- Pequenos e classificação continuam limitados. Melhores SBD/DoG/LoG
  localizam3/0/5 pequenos; melhor DoG rotula1.275 normais como pequenos.
  A fronteira indivíduo/aglomerado também bloqueia alguns candidatos válidos
  geometricamente, mas não houve novo pareamento nem correção de classes.

Direção recomendada ao concluir a análise: refinamento local de área/caixa
no SBD, região interna de resposta no DoG e investigação criteriosa de
pequenos e da fronteira entre grupos no LoG. Naquela etapa, a lista ainda
não havia sido escolhida. O plano posterior está no ponto de retomada acima.

Esta etapa registrou análise e estatísticas; não alterou executores, parâmetros,
anotações ou resultados. O documento completo de blobs continua previsto
após round5, antes da seleção em outras imagens e dos vídeos.

## Registro do round3 e da preparação do round4

Round3 concluído e analisado; round4 foi preparado e depois executado.
Ver [análise do round3](analise_round3_blobs.md),
[estatísticas com 56 contrastes](estatisticas_round3_blobs.json) e
[plano do round4](plano_round4_blobs.md).

- Batch round3: `batch__20260920T225209430564Z`; 24×178=4.272 avaliações,
  30.046 hashes de saídas e 361 origens íntegros. PDF de quatro páginas.
- Quatro controles reproduziram 712 avaliações, 17.502 detecções e
  3.560 arquivos. Entradas, dependências e detectores iguais aos do round2.
- Melhor F1: SBD r3c09, **0,567571**, ante 0,556433. Diferença +0,011139,
  intervalo exploratório por vídeo [−0,005867;+0,029797]; oito vídeos melhores,
  quatro piores. Interação área × margem sustenta novo refinamento.
- DoG r3c24: F1 **0,544980**, 2.402 normais e nenhum pequeno localizado.
  Dos normais encontrados, 1.275 foram classificados como pequenos.
  F1 de localização e classificação continuam separados.
- LoG r3c18: F1 **0,428430**, cinco pequenos e 14 aglomerados localizados.
  Com resposta0,08, LoG encontrou17 pequenos; preservar essa faixa no round4.
- As caixas melhoraram de forma verificável: mesmos candidatos brutos nos
  12 pares de margem e nas pontes LoG/DoG de resposta0,05 com o round2.

**Round4:** seis SBD (área48/64/80 × margem2/3, distância6), oito DoG
(resposta0,12/0,16/0,20/0,24 × margem6/8) e quatro LoG
(resposta0,08/0,12 × margem5/6). Cinco controles e 13 novas; 109 distintas
acumuladas. Mesmos 178 quadros e critérios. Sem CLAHE, nova escala ou classificação.

Passaram **110 testes distintos**, a conferência das entradas e a reprodução
idêntica do plano. O PDF foi revisado com dados sintéticos. Round4 não foi
executado durante a preparação; são **3.204 avaliações previstas**.

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round4
```

A conferência posterior está na [análise do round4](analise_round4_blobs.md).
O comando acima reproduz essa rodada; não inicia o round5.

## Registro do round2 e da preparação do round3

O round2 foi executado e analisado. O round3 foi então preparado e
posteriormente executado conforme o registro acima. A
[análise completa](analise_round2_blobs.md) e as
[estatísticas reproduzíveis](estatisticas_round2_blobs.json) registram as evidências.

- Batch round2: `batch__20260920T203403161690Z`; 32×178=5.696 avaliações,
  41.489 hashes de saídas e 360 origens íntegros; PDF de quatro páginas.
- Quatro controles reproduziram exatamente as 712 avaliações anteriores e
  18.961 detecções nos campos comuns. Nenhuma mudança de critério.
- Melhor F1: r2c11, 0,556433, ante 0,551828 da referência. Área mínima 48
  retirou 276 FP, mas perdeu 81 TP; melhora pequena e variável por vídeo.
- Distância 6 (r2c14): F1 0,555359, oito vídeos melhores e quatro empatados,
  sem piora; hipótese mais consistente para refinamento.
- Bootstrap pareado por 12 vídeos, 10.000 reamostragens, seed42: ΔF1 área48
  [−0,020448;+0,034656]; distância6 [+0,001480;+0,005889]. Intervalos
  exploratórios, sem prova de generalização ou correção da busca adaptativa.
- CLAHE perdeu nas oito comparações agregadas. Decisão: retirar essa frente
  do round3, preservando código e histórico.
- LoG/DoG: F1 0,086331/0,090275; muitos FP, mas o aumento da resposta
  retirou dezenas de milhares de FP com poucas perdas de TP. Muitos candidatos
  próximos de pequenos têm caixas insuficientes; centros não são novos acertos.
- DoG na grade atual não alcança diâmetro para classe1. Essa limitação está
  explicitada; aumentar sigma será uma investigação separada.

**Round3 aprovado:** 12 combinações SBD (área32/48/64 × distância6/12 × margem3/4)
e 12 LoG/DoG (cada método × resposta0,05/0,08/0,12 × margem4/6).
São quatro repetições, 20 novas e 96 distintas acumuladas, dentro do orçamento.
Ver [desenho completo e preparação](proposta_round3_blobs.md) e
[plano congelado](../scripts/blobs/rodadas/round3.json).
O executor e o PDF aceitam a terceira versão do plano, preservando a leitura
das anteriores. Controles: r3c02→r2c14, r3c03→r2c06, r3c04→r2c01 e
r3c08→r2c11. A quarta página do PDF compara as margens em 12 pares da rodada.
São 4.272 avaliações previstas; nenhuma foi executada durante a preparação.
Passaram 85 testes sintéticos e a conferência real das 178 entradas.
O PDF de quatro páginas foi revisado com dados sintéticos; os planos anteriores
e os resultados existentes foram preservados.

Comando para reproduzir o round3, na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round3
```

A conferência posterior está na [análise do round3](analise_round3_blobs.md).

## Registro da preparação anterior

O round1 foi concluído e analisado; o round2 foi preparado e posteriormente
executado conforme o registro acima. O [plano do round1](../scripts/blobs/rodadas/round1.json) contém
48 configurações distintas — 12 controles e 36 exploratórias — nos mesmos
178 quadros, totalizando 8.544 avaliações concluídas no batch
`batch__20260920T193937586038Z`. Os 60.056 hashes de saídas e o PDF de oito
páginas foram conferidos, sem divergências.

A [análise do round1](analise_round1_blobs.md) registra os resultados e a
proposta inicial do round2. Melhor configuração: r1c29,
F1 de indivíduos 0,551828, precisão 0,503554 e recall 0,610339. Localizou
2.194/3.464 normais, 2/134 pequenos e 0/109 aglomerados. Dos 1.402 FN de
indivíduos, 602 não têm centro candidato dentro da anotação e 736 têm
centro do grupo correto sem caixa de IoU suficiente. Ampliar todas as caixas
ou apenas mudar a classe 0/2 não resolve esses dois problemas.

Após aprovação de CLAHE e LoG/DoG, o [round2 definitivo](plano_round2_blobs.md)
foi congelado com **32 configurações**: quatro repetições (r1c29/23/26/43),
12 refinamentos isolados, oito CLAHE pareados e oito sondagens LoG/DoG.
São 28 novas, somando 76 distintas. Mantêm-se os 178 quadros, as métricas e
o orçamento de cinco rounds. LoG/DoG entram depois e têm menor esforço de
busca até aqui; não esconder essa diferença. Round1 não é reiniciado.

O preflight do round2 passou: 5.696 avaliações previstas, sem detectar nem
criar resultados. scikit-image 0.26.0 já estava instalado. Código e integração
foram testados somente com imagens sintéticas. A documentação técnica está
no plano, e os comandos estão no [guia de blobs](../scripts/blobs/README.md).

O PDF também foi reformulado após aprovação: quatro páginas com gráficos
ordenados, cobertura, mapa por vídeo e controles. Uma nova versão do round1
foi gerada em `relatorios/20260920T202745884789Z/relatorio.pdf`, dentro do
batch completo acima. O PDF anterior de oito páginas e as métricas permanecem
preservados; `relatorio.json` aponta para o novo. O formato fica automático
para round2, com as métricas atuais, sem retornar ao macro-F1 histórico.

A tentativa `batch__20260920T192425152218Z` terminou com `falhou` após
11 configurações completas e 87 quadros da 12ª: 2.045/8.544 avaliações.
O erro foi `PermissionError / WinError 5` na substituição de `execucao.json`.
Os 13.761 hashes das 11 configurações completas foram conferidos, sem
ausências ou divergências. As saídas parciais da 12ª não integram esses hashes.
Não houve PDF. O bloqueio pode ser temporário; seu responsável não foi identificado.

O salvamento do executor e do relatório passou a repetir a troca de arquivos
nos erros Windows 5/32/33, com espera limitada; erro persistente é propagado.
Não há retomada automática nem mudança de parâmetros. Reexecutar cria outras
pastas; os resultados anteriores não precisam ser apagados. A tentativa
interrompida permanece no histórico do esforço experimental.
Passaram 33 testes da correção: 7 específicos de arquivos e 26 do executor
e relatório. A rodada não foi executada novamente durante esse ajuste.

As caixas pequenas e os candidatos excedentes são problemas de desempenho
identificados pelo round0. Não são um erro de formato nem motivo para exigir
uma calibração completa antes das rodadas. As hipóteses de melhoria devem
entrar nas configurações da busca formal, com referência original e orçamento.

O plano anterior detalhava revisão, filtros, caixas e classificação como
etapas anteriores ao round1. A continuidade acordada incorpora esses estudos às
rodadas, sem exigir F1 mínimo para começar. Revisões visuais adicionais ficam
limitadas a dúvidas concretas; não é necessário classificar manualmente todos
os candidatos para avançar.

## Objetivo e limites

- Comparar detectores de espermatozoides contra as anotações da VISEM-Tracking.
- Métodos clássicos previstos: limiarização manual/Otsu, blobs e Watershed.
  k-NN fica para a abordagem híbrida; métodos modernos serão tratados depois.
- Primeiro imagens, depois vídeos completos. Nesta fase, vídeo significa
  detecção quadro a quadro; não há associação temporal de indivíduos.
- Preservar posições, medidas, origem, unidades e identificação dos quadros
  para estudos futuros de movimento. Índice de detecção não é identidade.
- Rastreamento, velocidade e predição de comportamento são trabalhos posteriores.

## Decisões vigentes de representação e avaliação

1. Anotações são caixas no formato YOLO, com classes **0 normal, 1 aglomerado
   e 2 pequeno (`small_or_pinhead`)**. Originais não são alterados.
2. Indivíduos 0/2 são pareados juntos; aglomerados 1 são pareados separadamente.
   A localização aceita uma troca 0↔2, registrada como erro de classificação
   somente nos pares válidos. Trocar indivíduo e aglomerado afeta o grupo.
3. IoU ≥ 0,50, correspondência exclusiva um para um. Somar TP, FP e FN antes
   de calcular F1. Priorizar **F1 de indivíduos**, com cobertura por classe,
   resultados por vídeo e erros de classificação apresentados separadamente.
4. Ausência de anotações e previsões significa “sem casos”. Previsões sem
   anotações contam como FP e dão F1 zero.
5. Empates exatos permanecem empates para revisão conjunta; não há atualmente
   peso maior da classe 0, desempate estatístico ou piso de recall aprovado.
6. Centro dentro de caixa é diagnóstico geométrico, não novo acerto ou recall.

O macro-F1 das três classes e o desempate pelo F1 normal pertencem ao protocolo
histórico. A regra atual foi aprovada após observar a primeira seleção da
limiarização; essa mudança está documentada e não deve ser apagada.

## Conjuntos e ciclo comum

| Etapa | Dados | Regra |
|---|---|---|
| Round0 de blobs | Seis quadros de desenvolvimento; duas configurações | Inspeção técnica e hipóteses; concluído |
| Rounds1–5 | 178 JPEGs dos vídeos 11, 12, 15, 19, 21, 22, 23, 30, 35, 36, 47 e 60 | Mesmos quadros para todas as configurações; ajustes somente aqui |
| Seleção em imagens | 60 JPEGs dos vídeos 13, 29, 52 e 54 | Comparar todas as configurações distintas congeladas; revisar cinco finalistas |
| Vídeos de seleção | MP4 completos 13, 29, 52 e 54 | Executar as cinco; mesmos vídeos da seleção em imagens |
| Vídeos finais | MP4 completos 14, 24, 38 e 82 | Mesmas cinco congeladas; avaliação descritiva sem novos ajustes |

JPEGs: quadros 0, 100, …, 1400. No desenvolvimento foram excluídos, de forma
acordada, 900 e 1100 do vídeo 23 por ausência de anotação. Nos vídeos, conferir
a correspondência e a presença das anotações previstas no plano antes de
avaliar. Entrada prevista ausente ou divergente interrompe a execução;
não há exclusão automática. Ausência de arquivo não significa ausência de objetos.

Os vídeos finais e parte do histórico já foram vistos. Manter os conjuntos
permite comparações, mas não cria um teste inédito. Vídeos de seleção também
não são independentes de seus JPEGs. O maior F1 final não escolhe
retroativamente uma configuração nem comprova superioridade estatística.

## O que já foi concluído

**Limiarização:** round0, cinco rodadas (48/32/24/18/14 configurações), seleção
de 122 configurações distintas, reavaliação por indivíduos, cinco finalistas
e vídeos de seleção/finais. Finalistas: s068, s067, s090, s099 e s101.
Maior F1 final de indivíduos: 0,566796, empate de s099/s101; nenhuma das duas
localizou as 2.936 ocorrências de pequenos. Ver
[conclusão e limitações](conclusao_limiarizacao.md). Macro-F1 histórico e F1
de indivíduos atual não formam uma única curva de melhoria.

**Blobs:** [detector](../algoritmos/classicos/blobs.py), contrato de medidas,
exportação YOLO, [executor da inspeção](../scripts/blobs/executar_inspecao.py),
avaliação, comparações, PDF e [diagnóstico dos registros](diagnostico_round0_blobs.md).
A inspeção de duas configurações × seis quadros permanece preservada. O
[executor de rodadas](../scripts/blobs/executar_rodada.py) e o
[adaptador de caixas](../algoritmos/classicos/caixas_blobs.py) foram acrescentados
separadamente para o round1.

- Origem: `resultados/frame-to-frame/blobs/round0/inspecao__20260920T041252237886Z`.
- Diagnóstico: `resultados/frame-to-frame/blobs/round0/diagnostico__20260920T175946938558Z`.
- Quadros: 11/0, 12/200, 19/0, 21/0, 23/0 e 36/1300.
- Referência por configuração: 160 normais, 7 pequenos e 5 aglomerados.
- b01 (claros): 619 detecções; F1 de indivíduos 0,005188.
- b02 (escuros): 2.485 detecções; F1 de indivíduos 0,001516.
- 3.104 caixas conferidas: conversão, recorte e exportação coerentes.
- Entre indivíduos com um único centro, a área mediana prevista/anotada foi
  17,50% em b01 (101 casos) e 9,21% em b02 (55 casos).
- Exemplos visuais e relações geométricas sustentam investigar tamanho,
  candidatos excedentes, multiplicidade e pequenos; não validam uma correção.
- Diagnóstico 12/12 concluído, 36 testes sintéticos específicos aprovados;
  integridade dos arquivos de origem e saídas conferida. As demais suítes não
  foram reexecutadas na entrega do diagnóstico; as regressões posteriores
  do round1 estão registradas abaixo. A ficha humana permanece sem pareceres.

O blob retorna centro e diâmetro estimados. A caixa original usa esse diâmetro
como lado, com arredondamento e recorte. O adaptador oferece escala ou margem,
preservando centro, diâmetro, área circular, classe e ordem dos candidatos.
Área circular estimada, área da
caixa e área interna do filtro são medidas distintas. Não há máscara da
cabeça; medidas que dependem dela ficam ausentes, não são inventadas.

## Histórico da preparação do round1 e continuidade acordada

1. **Encerrar o round0 como inspeção concluída**, preservando suas limitações.
2. **Executor e plano do round1 preparados**, reutilizando o avaliador,
   os 178 quadros e a estrutura de resultados, com tabelas, comparações,
   manifestos, código arquivado e PDF. A opção `--conferir` verifica plano,
   dependências, hashes e imagens antes de qualquer detecção, sem criar resultados.
3. **Caixas aprovadas:** manter a original e acrescentar alternativas de
   **escala do diâmetro** ou **margem fixa**, sem combiná-las inicialmente.
   Cada combinação completa é uma configuração e entra no orçamento.
   Escala e margem estão implementadas em módulo separado. Nenhuma variante
   foi declarada superior nem congelada como escolha final.
4. A nova suíte integrada passou em **66 testes sintéticos**, incluindo
   identidade da caixa original, bordas, medidas brutas, planejamento,
   executor e relatório. Também passaram **113 testes de regressão**, totalizando
   **179 testes**. As oito páginas do PDF sintético foram revisadas. A
   conferência real `--conferir` passou para as 48 configurações e os 178
   quadros, sem detecção nem criação de resultados. Isso verifica a implementação,
   não o desempenho na base. Se necessário um piloto
   real do executor, usar o subconjunto já conhecido do round0, registrar a
   execução e não transformar esse piloto em outra busca de parâmetros.
5. **Executar o round1 amplo:** 12 controles vinculados a b01/b02 e 36
   combinações exploratórias de parâmetros do detector, tamanho da caixa
   e limites de classificação, com hipóteses explícitas e seed 42.
   Não fixar um fator “ideal” usando apenas seis imagens.
6. **Rounds seguintes:** concentrar tentativas em regiões promissoras,
   conservar controles e alguma exploração de alternativas. Rever efeitos
   por vídeo/classe e interações; não seguir exclusivamente uma vencedora.
7. **Após concluir e analisar o round5, produzir um relatório do desenvolvimento
   de blobs**, antes da seleção: implementação e adaptações das caixas,
   decisões de comparação e seus motivos, configurações e hipóteses de cada
   rodada, resultados que orientaram a seguinte, reprodução e limitações.
   Separar decisões tomadas antes dos testes de mudanças motivadas pelos resultados.
8. Encerrar no orçamento combinado, congelar candidatas e seguir seleção e
   vídeos. Ganho por rodada não é garantido; resultado insuficiente também
   deve ser documentado, sem ampliar indefinidamente o método.

**Orçamento aprovado:** até cinco rodadas, **48/32/24/18/14**, total de
136 execuções de configuração nos 178 quadros, incluindo controles repetidos,
com teto de 122 configurações distintas. A adaptação de caixa não multiplica
esse teto por três. Inspeções adicionais ficam registradas no esforço total.
O round1 usa seed 42 na geração do plano. A lista final de configurações,
quadros, hashes e versões é a referência de reprodução; seed sozinha não basta.

O pesquisador confirmou os modos, o orçamento e a implementação do round1
em 20/09/2026. As faixas e as 48 combinações foram justificadas e registradas
no plano. O executor lê essa lista, sem sorteio ou ajuste durante a rodada.
A primeira tentativa real foi interrompida conforme o registro acima; sua
repetição completa e análise estão concluídas. A definição numérica do
round2 agora está definida no plano específico, preparado após essa análise.

Não é necessário melhorar candidatos, caixas e classificação completamente
antes do round1. A condição para começar é ter implementação verificável,
saídas comparáveis, plano explícito e recursos para executar a rodada.
O ajuste de desempenho é justamente o trabalho das rodadas.

### Reprodução do round2 concluído

A [descrição do round2](plano_round2_blobs.md) registra o desenho e os motivos.
O [plano JSON](../scripts/blobs/rodadas/round2.json) é a lista congelada para
execução; não contém resultados. A infraestrutura mantém:

- Regra de caixa separada do parser do detector e dos planos do round0;
  original, escala 1 e margem 0 são equivalentes.
- Um executor de rodadas, com resultados em pastas novas, parâmetros originais
  e efetivos, caixas originais e adaptadas, medidas brutas e código arquivado.
- Relatório por configuração, classe e vídeo, com PDF regenerável a partir
  das tabelas salvas, sem repetir o detector.
- **32 configurações completas**, incluindo todos os métodos, processamentos
  e caixas; nenhum fator adicional multiplica esse total.

Na raiz do projeto, a conferência técnica e a execução são comandos separados:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round2 --conferir
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round2
```

A conferência não executa o detector. O segundo comando realiza a rodada;
o pesquisador já o executou. Esses comandos reproduzem o round2; não são
a próxima etapa. Round3 a round5 foram concluídos; a continuidade atual está
no ponto de retomada acima.

Na geração e filtragem, os eixos disponíveis são faixa/passo de limiar,
repetibilidade, distância, área interna e filtros de forma. A caixa acrescenta
modo e tamanho; a classificação mantém limites próprios sobre a área estimada.
As combinações devem explorar efeitos conjuntos, com controles para interpretar
os resultados. Segmentação local, k-NN e novos avaliadores não entram nesta entrega.

## Pesquisa que orienta a proposta

O OpenCV descreve a saída do SimpleBlobDetector como pontos com centro e
tamanho estimados; `KeyPoint.size` representa um diâmetro. A documentação não
define uma caixa biológica. Nossa conversão é uma escolha do método, cujo
desempenho deve ser medido contra a referência mantida.
[SimpleBlobDetector](https://docs.opencv.org/4.13.0/d0/d7a/classcv_1_1SimpleBlobDetector.html),
[KeyPoint](https://docs.opencv.org/4.13.0/d2/d29/classcv_1_1KeyPoint.html).

A busca aleatória é uma referência fundamentada para explorar hiperparâmetros
com orçamento limitado. A aplicação implementada é amostragem reproduzível e
equilibrada entre as famílias no round1, seguida de refinamento documentado;
isso é uma escolha deste estudo, sem garantia de vantagem para blobs.
[Bergstra e Bengio, 2012](https://www.jmlr.org/papers/v13/bergstra12a.html).

O ajuste repetido ao mesmo conjunto pode favorecer escolhas que exploram
particularidades da amostra. Por isso, limitar tentativas e separar ajuste,
seleção e avaliação continua relevante, reconhecendo a exposição anterior.
[Cawley e Talbot, 2010](https://www.jmlr.org/papers/v11/cawley10a.html).

## Arquivos para retomar sem reconstruir a conversa

- [Protocolo vigente e histórico](protocolo_rodadas.md).
- [Diagnóstico e exemplos do round0](diagnostico_round0_blobs.md).
- [Plano geral de blobs](plano_blobs.md) e [hipóteses de melhoria](plano_diagnostico_blobs.md).
- [Guia de comandos de blobs](../scripts/blobs/README.md).
- [Plano congelado da inspeção](../scripts/blobs/inspecao/round0.json).
- [Plano congelado do round1](../scripts/blobs/rodadas/round1.json) e
  [desenho e comandos](plano_round1_blobs.md).
- [Reprodução da limiarização](../README.md) e [análise consolidada](conclusao_limiarizacao.md).

Saídas de imagens: `resultados/frame-to-frame/<algoritmo>/<round>/`.
Configuração e execução identificam cada pasta. Vídeos ficam em
`resultados/videos/<algoritmo>/<etapa>/`. Preservar resultados anteriores,
originais e arquivos arquivados; o pesquisador executa os novos experimentos,
salvo autorização específica em contrário.

Branch atual: `apenasavaliacao-deteccao`. `AGENTS.md` e resultados ficam fora
do Git. Há uma edição preexistente de `scripts/configuracoes/limiarizacao.modelo.json`
que não pertence ao trabalho de blobs e deve ser preservada. Esta etapa
acrescentou as variantes autorizadas, o plano round2 e o novo formato do PDF.
Nenhum experimento real foi executado nesta preparação. Novas etapas e
commits seguem o escopo explicitamente acordado.

Permanece prevista, para outra ocasião, uma apresentação completa do percurso
do projeto em HTML. Esta síntese é um registro de continuidade, não substitui
os resultados, planos congelados e justificativas detalhadas das rodadas.
O relatório de blobs após o round5 é uma entrega específica solicitada pelo
pesquisador; explica o que foi feito e por que cada decisão foi tomada.
O desenvolvimento está documentado em HTML; a seleção e os vídeos foram
posteriormente concluídos, conforme o ponto de retomada e a conclusão acima.
