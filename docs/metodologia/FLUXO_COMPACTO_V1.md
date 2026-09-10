# Fluxo causal compacto — benchmark prospectivo e desenho da ablação

Registro de 09/09/2026, anterior aos pixels do benchmark. O nível 7 permanece
concluído e preservado. Este **nível 8a** prepara escala e integridade; não
avalia preditores, não mede ADE/FDE e não seleciona parâmetros de Farnebäck.

Plano executável: [compact_benchmark_v1.yaml](../../configs/flow/farneback/compact_benchmark_v1.yaml).
Hash canônico:
`f794175a7060b687099cfc391a02f71e8ba95bf2b18dc736a0e91be741eee0e1`.
Protocolo anterior: [fluxo causal v1](FLUXO_CAUSAL_V1.md).

## Por que mudar o armazenamento

O smoke anterior guardou todos os campos densos dos dois sentidos e todos os
quadros observados: 193.999.043 bytes para 38 pares. Repetir essa retenção em
todos os treinos pode ocupar dezenas de gigabytes; o prefixo não fornece um
benchmark confiável de vídeos completos. Tampouco é necessário recalcular o
mesmo campo para cada trajetória ou repetir o vetor em cada janela sobreposta.

As 343.776 janelas auditadas implicam 6.531.744 usos históricos de fluxo
(19 por janela), mas apenas **354.990 amostras distintas** na união dos
históricos. Para cada segmento com W janelas consecutivas, a união contém
W+18 transições. Assim, 343.776 + 18×623 = 354.990. Essa conta deriva dos
índices da referência; não é resultado de fluxo nem nova preparação dos dados.

Cada amostra é identificada por `(vídeo, ID original, segmento, frame_from)`.
O identificador é o SHA-256 completo da lista JSON compacta dessas quatro
chaves. As 19 referências ordenadas de cada janela ficam em uma tabela de
ligações, mantendo a janela original como unidade de previsão. Igualdade de
chaves não basta: coordenadas de amostras repetidas devem coincidir exatamente.
Segmentos distintos não são unidos, mesmo quando compartilham ID original.

## Amostra e limites prospectivos

- Todos os 12 treinos, em ordem fixa: 11,12,13,15,21,22,23,29,30,35,60,82.
- Prefixo **0..59**, 60 leituras sequenciais por vídeo, sem seek ou quadro 60.
  Resolução original 640×480; FPS e total de quadros vêm do pai autenticado.
- Todas as janelas da referência com origem 19..59, inclusive, mantendo
  histórico de 20 posições e elegibilidade futura de 10 posições. Nenhuma seleção por fluxo, erro,
  velocidade ou classe adicional. Prefixo sem janela faz falhar, sem substituição.
- Estimar os **59 campos forward** de cada vídeo. Estimar backward e manter
  campos densos somente nos pares fixos **0→1 e 58→59**.
- Totais exigidos: **720 quadros, 708 campos forward, 24 backward, 24 pares
  densos preservados e 48 quadros cinza preservados**.
- Farnebäck mantém os parâmetros iniciais do nível 7: pyr_scale=0,5, levels=4,
  winsize=21, iterations=5, poly_n=7, poly_sigma=1,5, gaussiana. CPU, uma thread,
  OpenCL desativado, seed 42, sem máscara, recorte ou redimensionamento.
- Teto do benchmark: **900 s**, **2.048 MiB RSS amostrado**, **512 MiB artefatos**.
  Falha, incompletude ou estouro preservam os parciais e impedem a conclusão.

Esse desenho repete parte dos pixels dos prefixos 11/12 em uma **nova execução
de custo e armazenamento**, necessária para medir o novo produtor. Não reabre
ou sobrescreve o smoke encerrado e não reutiliza seu cache para simular custo
de estimação. Os 12 prefixos não representam todas as condições dos vídeos.
As lacunas posteriores do vídeo 23 continuam preservadas na referência; não
se infere sua cobertura a partir destes primeiros 60 quadros.

## Causalidade e leitura da referência

O iterador `VideoReference.iter_history_batches` percorre as chaves uma vez,
entregando somente blocos de posições históricas e metadados de janela. Não
usar `iter_batches`, que também retorna alvos. As coordenadas futuras não são
fatiadas nem entregues ao produtor compacto. O pai contém informação futura
para elegibilidade retrospectiva; isso não a torna entrada do preditor.

Todas as requisições dos prefixos são fixadas antes de abrir o primeiro MP4.
O campo F_s representa s→s+1, fica disponível em s+1 e é amostrado em p_s.
O último par do prefixo é 58→59. Uma janela de origem t referencia somente
os pares t−19→t−18 até t−1→t, nunca t→t+1.
O estimador recebe apenas as duas imagens correspondentes, sem centros ou GT.
Os centros históricos entram exclusivamente na amostragem posterior.

Conversão para cinza uint8 usa `as_gray_u8`, helper NumPy já existente.
OpenCV decodifica os MP4s e estima os campos float32. Coordenadas, pesos e
amostras interpoladas permanecem float64. Não arredondar centros, aplicar
clipping às coordenadas ou usar o consumidor legado com fluxo futuro observado.

## Testemunhos e rastreabilidade

Guardar apenas o vetor final impediria conferir sua interpolação. Por isso,
cada amostra preserva os quatro vizinhos consultados, na ordem 00, 10, 01, 11:
índices inteiros, vetores float32 e validade booleana. Os pesos são reconstruídos
das coordenadas float64. Na última coluna/linha, o vizinho superior coincide
com a borda, conforme o contrato bilinear anterior. Vizinhos de peso zero são
preservados, mas não contribuem nem invalidam a amostra.

Fora da imagem, o testemunho guarda índices −1, vetores NaN e validade False.
Um vetor inválido mantém seu registro, motivo e células u/v vazias no CSV.
Zero válido permanece zero. Dentro da imagem, todos os vizinhos de peso
positivo devem ser válidos e finitos. Não usar limiar de qualidade para excluir.

Os testemunhos ficam em um NPZ por vídeo, sem pickle, com arrays e metadados
tipados, ligados por hash ao manifesto. O índice contém o hash dos cinzas de
todos os 60 quadros e dos 59 campos forward, calculado sobre bytes contíguos.
O hash do campo usa bytes float32 do fluxo seguidos dos bytes booleanos de
validade. Dimensões, vídeo, fonte e configuração estão no índice autenticado.
Nos sentinelas, o NPZ denso conserva o contrato exato do nível 7.

**Limite da conferência compacta:** os quatro vizinhos permitem reconstruir
todas as interpolações. Nos sentinelas, também é possível confrontá-los com
o campo denso. Fora dos sentinelas, a origem desses valores depende do produtor
registrado e de seus testes: o hash de um campo descartado não o reconstrói
nem prova, sozinho, que os vizinhos pertenciam a ele. Não haverá reexecução
independente do estimador ou segunda decodificação dos MP4s neste QA.

## Saídas organizadas

Nova run em `data/tests/flow/farneback/<configuração>/benchmark/<run>/`.
Cada `by_video/<id>/` contém:

| Arquivo/pasta | Papel |
|---|---|
| `selected_windows.csv` | Todas as janelas selecionadas, com chaves do pai. |
| `requests.csv` | Centros de origem deduplicados, par e identidade. |
| `links.csv` | As 19 amostras ordenadas por janela, como JSON em célula CSV. |
| `features.csv` | Valores, validade e motivo de ausência por amostra única. |
| `window_coverage.csv` | Cobertura das 19 e das 5 finais, elegibilidade futura da ablação. |
| `witnesses.npz` | Identificadores, coordenadas, quatro vizinhos e metadados. |
| `frame_index.json` / `pair_index.json` | Índices e hashes de todos os quadros/pares do prefixo. |
| `frames/` / `checkpoints/` | Somente os cinzas e campos dos dois sentinelas fixos. |
| `checkpoint_metrics.csv` | Fotometria, suporte e FB dos sentinelas, sem filtro. |
| `summary.json` | Contagens, cobertura e componentes de custo daquele vídeo. |

Manifesto e resumo globais registram integridade, ambiente, orçamento e
projeção. Nenhuma saída substitui as fontes, a referência, os baselines ou o
smoke anteriores. Não gerar predictions.csv ou calcular ADE/FDE nesta entrada.

## Diagnósticos e cobertura

Fotometria em cinza/255 compara warp e deslocamento zero no mesmo suporte.
Consistência forward/backward usa resíduo F(p)+B(p+F(p)), média, fração ≤1,5 px
e denominadores explícitos. São **dois sentinelas por vídeo**, não média dos
59 pares ou avaliação completa. Este benchmark não calcula mudança temporal,
EPE real, ranking, p-valor ou intervalo de confiança.

Todas as janelas mantêm contagem de validade das 19 transições. A ablação CV
posterior exigirá somente as **cinco últimas amostras**, efetivamente usadas
na fórmula; invalidez nas 14 anteriores não a excluirá silenciosamente. Os
dois preditores deverão receber exatamente a mesma coorte elegível. A média
histórica das 343.776 janelas não substitui a comparação nesse subconjunto.

## Projeção registrada antes dos resultados

Por vídeo v, sejam P_v=N_v−1 pares completos, U_v amostras únicas completas,
W_v janelas completas e u_v,w_v suas contagens no benchmark.

- `loop_scale = max(P_v/59, U_v/u_v)`.
- `table_scale = max(W_v/w_v, U_v/u_v, N_v/60, P_v/59)`.
- Tempo projetado: duas vezes a soma do custo fixo observado com
  `loop_seconds*loop_scale + table_seconds*table_scale + checkpoint_seconds`
  dos 12 vídeos.
- Bytes projetados: duas vezes
  `sum(compact_bytes*table_scale + checkpoint_bytes)`, mais reserva de 16 MiB
  para resumos e manifestos. Os bytes por vídeo são medidos antes de seu resumo.

O laço inclui decodificação, estimação forward, amostragem e coleta de
testemunhos. Os checkpoints incluem os dois backward, métricas e campos/quadros
retidos. As tabelas incluem construção dos índices compactos, exportação,
autenticação dos artefatos e sua rechecagem final. Leitura do pai completo,
hashes dos MP4s completos e demais custos fixos entram uma vez. O fator máximo
entre pares e densidade evita projetar todos os custos apenas pelo número de
quadros. Denominador zero torna a projeção indisponível, nunca custo zero.

Limites de planejamento: **7.200 s e 4.096 MiB de artefatos projetados**. Estar
abaixo deles será apenas um **indicador provisório de viabilidade**. Ainda
serão necessários QA independente e plano operacional para a extração completa,
com política de retenção de índices e memória. O RSS do prefixo não certifica
o RSS das tabelas completas. Não extrapolar automaticamente cobertura, qualidade
ou densidade dos prefixos para vídeos inteiros. Não iniciar a extração completa
por esta CLI, mesmo se o indicador passar.

## Desenho da primeira ablação — ainda sem execução

O novo [preditor causal](../../src/prediction/hybrid/causal_constant_velocity.py)
adapta a ideia do [híbrido legado](../../src/prediction/hybrid/constant_velocity_with_flow.py)
sem reutilizar sua entrada permissiva, aritmética float32 ou fluxo futuro.
Para s=t−5..t−1, fixar g_s=F_s(p_s) e:

`v = mediana_por_componente(Δp_s − g_s) + g_(t−1)`;
`p_estimado(t+h) = p_t + h*v`, para todos h=1..10.

Isso extrapola um resíduo algébrico e mantém o último deslocamento aparente
constante no futuro. Não estima velocidade intrínseca da célula ou do fluido.
O controle sem fluxo é `cv_median5`, usando os mesmos cinco deslocamentos e
mesmas seis posições, dentro do histórico comum de 20 posições. Quando g_s é constante,
subtração e reposição devem cancelar-se e reproduzir o baseline dentro da
tolerância numérica. Outros casos sintéticos verificam mudanças de fluxo,
pares futuros, lacunas, ausência, precisão e previsões fora da imagem.

O contraste fixo não tem busca, ajuste ou normalização. Sua futura avaliação
será descritiva no treino, nas mesmas janelas elegíveis, com ADE denso 1..H e
FDE em H=1/5/10, em pixels. Agregação principal: janelas por ID original,
reunindo segmentos; peso igual entre IDs dentro de vídeo; depois entre vídeos.
IDs/vídeos sem janela elegível não receberão erro zero e exigem cobertura
explícita. Essa ablação clássica não substitui LSTM com/sem fluxo, RAFT,
rastreamento/HOTA ou avaliação fora da amostra previstos no TCC.

## Conclusão técnica exigida

Registrar código e plano antes dos pixels, após testes sintéticos do núcleo,
do executor, das projeções e da conferência independente. A run deve concluir
todos os 12 prefixos, preservar todas as janelas, reconciliar deduplicação e
ligações, conferir hashes de fontes/pais/saídas e reconferir Git/ambiente.
O QA posterior deve reconstituir chaves e coordenadas a partir dos derivados
do pai, verificar todos os testemunhos e amostras, confrontar campos densos
nos sentinelas, recomputar métricas, suporte, cobertura e projeção.
Coordenadas, contagens e hashes exatos; tolerância absoluta 1e-9, relativa 0,
para interpolações e diagnósticos. Preservar falhas em novos arquivos de QA.
Não declarar o nível 8 inteiro concluído: o marco 8a apenas prepara sua execução.


## Resultado do benchmark — 09/09/2026

**Nível 8a concluído e conferido; extração completa bloqueada pelo orçamento
de tempo.** Código, plano e verificador foram registrados antes dos pixels em
`6110c44526c30f8f8f7a2fdeb276f7169d2fcd88`, após **1.728 testes em 181,93 s**
e self-test independente. A run terminou com Git limpo, reconferido ao final.
O identificador usa UTC em 10/09; a execução ocorreu em 09/09 no fuso de São Paulo.

Os 12 prefixos concluíram 720 quadros, 708 campos forward e 24 backward.
Foram preservadas **10.848 janelas, 15.762 amostras distintas e 206.112 usos
históricos**. Todas as amostras foram numericamente válidas e todas as janelas
tiveram suas cinco amostras finais válidas. Isso não certifica acurácia do fluxo
ou cobertura dos vídeos completos. As 10.848 janelas não são réplicas independentes.

| Vídeo de treino | Janelas | Amostras distintas | Usos históricos |
|---|---:|---:|---:|
| 11 | 1.663 | 2.419 | 31.597 |
| 12 | 1.077 | 1.617 | 20.463 |
| 13 | 1.802 | 2.594 | 34.238 |
| 15 | 902 | 1.298 | 17.138 |
| 21 | 891 | 1.305 | 16.929 |
| 22 | 489 | 705 | 9.291 |
| 23 | 164 | 236 | 3.116 |
| 29 | 164 | 236 | 3.116 |
| 30 | 492 | 708 | 9.348 |
| 35 | 1.356 | 1.968 | 25.764 |
| 60 | 738 | 1.062 | 14.022 |
| 82 | 1.110 | 1.614 | 21.090 |
| **Total** | **10.848** | **15.762** | **206.112** |

O tempo da run foi **199,583442 s**, com **375,145 MiB RSS amostrado** em
734 observações. Foram guardados 193 artefatos e um manifesto: 153.909.176
bytes antes do manifesto final e **154.023.508 bytes finais**. Os 24 pares
sentinelas conservam ambos os sentidos e os 48 quadros cinza correspondentes.
Os parâmetros, o limite de 60 quadros e a coorte não foram alterados.

### Conferência independente

O QA passou na **primeira tentativa**: **288 arquivos**, **934.668 comparações**,
incluindo 127.506 numéricas e 94.572 de coordenadas, em **23,4658582 s**.
Máxima diferença numérica: `3,552713678800501e-15`, abaixo do limite absoluto
de 1e-9, sem tolerância relativa. Foram conferidos 7.372.800 pixels de pares
nos diagnósticos sentinelas e 14.745.600 pixels de campos direcionais retidos.
O QA reconstruiu todas as amostras a partir dos testemunhos e confrontou os
testemunhos sentinelas com os NPZ densos. Não reabriu MP4s ou labels originais,
não importou a implementação científica e não repetiu Farnebäck.
Fora dos sentinelas, os campos descartados continuam não reconstruíveis;
o vínculo dos quatro vizinhos ao estimador depende da procedência do produtor.

- [Manifesto da run](../../data/tests/flow/farneback/farneback_compact_benchmark_v1__cfgeae42bba/benchmark/20260910T023738734548Z__6110c44__cfgf794175a7060__srca19f8367f9__s42/manifest.json); SHA256 `72c7df2d895d1fa02014dfa1100a1a7defc8351ea19d86392ad09e5473fcd278`.
- [Conferência aprovada](../../data/tests/flow/farneback/farneback_compact_benchmark_v1__cfgeae42bba/benchmark/verification_20260909.json); SHA256 `20af88c5930434685a86330d98692f99d9a429f0e0e61723ae41138e1af1435c`.
- Hash das fontes de código da run: `a19f8367f992f31710d50dc6e17bec33cdbce4905eae3a8eb9bc6bb477e0c81d`.
- [Resumo global](../../data/tests/flow/farneback/farneback_compact_benchmark_v1__cfgeae42bba/benchmark/20260910T023738734548Z__6110c44__cfgf794175a7060__srca19f8367f9__s42/summary.json) e
  [saídas por vídeo](../../data/tests/flow/farneback/farneback_compact_benchmark_v1__cfgeae42bba/benchmark/20260910T023738734548Z__6110c44__cfgf794175a7060__srca19f8367f9__s42/by_video).
- Figura [PNG](../../data/derived/flow/reports/farneback_compact_benchmark_v1_20260909/benchmark_fluxo_compacto.png),
  [SVG](../../data/derived/flow/reports/farneback_compact_benchmark_v1_20260909/benchmark_fluxo_compacto.svg)
  e [proveniência](../../data/derived/flow/reports/farneback_compact_benchmark_v1_20260909/provenance.json).

### Orçamento e continuidade

A regra registrada projetou **8.052,675671 s (134,21 min)**, acima dos
7.200 s (120 min) permitidos: excesso de 852,675671 s, aproximadamente 11,84%.
Projetou **1.854.533.829,14 bytes (1.768,62 MiB)**, abaixo dos 4.096 MiB.
O estado é `exceeds_planning_budget`; `full_extraction_released=false` e
`full_rss_certified=false`. O próprio benchmark respeitou seus limites;
é a projeção de escala que não passou. Não elevar retroativamente o teto,
retirar o fator de segurança ou omitir parcelas para declarar aprovação.

Com o fator 2 já aplicado, o laço responde por 7.516,522034 s da projeção
(93,34%), as tabelas por 450,794378 s, os sentinelas por 43,485277 s e a
parcela fixa por 41,873983 s. O laço reúne decodificação, estimação,
amostragem e coleta de testemunhos; esses dados não isolam qual subetapa
domina. O próximo marco deverá instrumentar essas parcelas e registrar um
ajuste operacional verificável, se necessário, antes de qualquer novo ensaio.
Eventual paralelismo exige conferir equivalência numérica e recursos, mantendo
os parâmetros científicos, a causalidade e a referência. Isso é continuidade
proposta, não uma otimização já implementada ou um novo benchmark executado.

Após resolver o custo sob plano próprio, registrar a extração completa,
a retenção de índices/memória e a ablação pareada na coorte comum. O preditor
causal está implementado e testado sinteticamente, mas **não foi chamado em
dados reais**. Não há ADE/FDE com fluxo, seleção, promoção ou confirmação da
hipótese. Referência, baselines, smoke e este benchmark permanecem preservados.
