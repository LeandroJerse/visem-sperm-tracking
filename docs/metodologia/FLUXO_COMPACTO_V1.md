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
