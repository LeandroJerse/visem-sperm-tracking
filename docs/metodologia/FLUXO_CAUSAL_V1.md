# Fluxo aparente causal — contrato e smoke v1

Registro prospectivo de 09/09/2026, antes de ler os pixels deste ensaio.
Plano: [causal_smoke_v1.yaml](../../configs/flow/farneback/causal_smoke_v1.yaml).
O hash canônico do plano é
`f7e0afa345b3774127bb622a03ab21d1100dd9655dbd7bb0c6c3eaaa4f13708f`.

## Finalidade e posição no TCC

O nível 6 avaliou persistência e velocidade constante sobre trajetórias GT do
treino. Agora é necessário produzir características de imagem que estariam
disponíveis na origem da previsão. Este nível 7 verifica a conexão entre
imagem, par temporal, referência individual e amostragem local de Farnebäck.
Não executa preditor, não calcula ADE/FDE e não testa a hipótese com/sem fluxo.
Não faz busca, seleção, congelamento ou confirmação científica de Farnebäck.

O código legado de fluxo preserva uso exploratório, mas não basta para esta
cadeia: uma interrupção de decodificação podia encerrar um lote parcial; índices
antigos aceitavam vídeo ausente e não exigiam o hash do NPZ; a integração legada
não certificava quais pares estavam disponíveis na origem. Um consumidor
antigo de predição também admite fluxo futuro observado como oráculo. O novo
caminho é separado, com contrato explícito, sem reescrever experimentos antigos.

## Amostra fixada sem consultar desempenho

- Vídeos **11 e 12**, treino, nesta ordem. Não abrir validação/teste.
- Quadros **0 a 19**, resolução original 640×480; origem da previsão **t=19**.
- Exatamente 20 quadros devolvidos pelo decodificador e 19 pares consecutivos
  por vídeo: 0→1, 1→2, …, 18→19. Não solicitar o quadro 20.
- Para cada par, estimar forward e backward: 38 pares e 76 campos no ensaio.
- Selecionar **todas** as janelas da referência individual auditada com
  `history_start=0` e `origin_frame=19`. Não selecionar IDs por velocidade,
  imagem, cluster, erro ou validade de fluxo. Se não houver janelas, falhar
  antes de ler vídeos; não procurar outra origem.
- A seleção continua condicionada ao futuro completo do derivado pai. Isso
  serve à elegibilidade offline e não disponibiliza coordenadas futuras.
  `history_batch_at_origin` retorna apenas as 20 posições históricas e chaves.

O ensaio é curto e determinístico; não representa vídeos completos nem uma
amostra independente para inferência. Contagens de janelas/pares não ampliam
o número de vídeos. A referência e sua conferência são fixadas por hash no
plano; ela permanece intacta. Não reler os labels originais.

## Convenção temporal e espacial

`F_s[y,x]=(u,v)` representa deslocamento aparente de `(x,y)` no quadro s
para `(x+u,y+v)` no quadro s+1, em pixels por par. O campo fica disponível
em **s+1**, depois de observar ambas as imagens. Para prever depois de t,
exigir s+1≤t. Vinte posições fornecem 19 transições históricas.

Cada característica é `F_s(p_s)`, amostrada no centro histórico **do quadro
de origem s**, e não em p_(s+1). O último campo usado na origem19 é 18→19;
o campo19→20 usa uma imagem futura e é recusado. Backward estima o sentido
inverso com as mesmas duas imagens já observadas, apenas para diagnóstico.

Coordenadas de centro e pesos de interpolação são float64. O campo OpenCV é
preservado em float32, sua precisão nativa. A interpolação bilinear exige
coordenada finita dentro de `[0,W−1]×[0,H−1]` e todos os vizinhos com peso
estritamente positivo válidos e finitos. Um vizinho com peso zero não contribui.
Não arredondar centros, fazer clipping ou aceitar validade interpolada ≥0,999.

Este smoke usa somente a amostragem direta no centro. Anéis, máscaras,
remoção de cabeça/fundo e outras escalas locais exigem outro plano. Centros
GT históricos localizam a amostra; nenhum GT é fornecido ao estimador de fluxo.
Isso isola a extração sobre referência conhecida e não é avaliação fim a fim.

## Parâmetros e execução

Uma única configuração, herdada dos parâmetros iniciais já existentes:
`pyr_scale=0.5`, `levels=4`, `winsize=21`, `iterations=5`, `poly_n=7`,
`poly_sigma=1.5`, `gaussian=true`. Não há busca sobre o espaço legado.
Conversão BGR→cinza uint8 pelo helper existente, sem redimensionar, recortar,
estabilizar, normalizar por vídeo ou modificar contraste. Máscara ausente.

CPU, uma thread OpenCV, OpenCL desativado e seed42. Registrar versões,
backend, parâmetros, commit, Git limpo, hardware e tempo. Ler sequencialmente
desde o início, verificando metadados e dimensão de cada quadro. Read=False
antes do vigésimo quadro, salto de índice ou quadro incompatível falham a run.
O contrato certifica somente o prefixo de 20 quadros, não o resto do vídeo.
O arquivo MP4 completo é lido como bytes para conferir SHA-256, antes e depois;
isso não fornece suas imagens futuras ao estimador. Bibliotecas de codec podem
armazenar buffers internos; a aplicação recebe somente o prefixo registrado.

## Artefatos e consumidor protegido

Cada nova run fica em `data/tests/flow/farneback/`, sob configuração e `smoke/`.
Nada é sobrescrito. Dentro de `by_video/11` e `by_video/12`:

| Saída | Conteúdo e motivo |
|---|---|
| `frames/*.npy` | Os 20 quadros cinza observados, uint8, para auditar métricas sem reler MP4. |
| `frames.json` | Índice, SHA-256, dimensões e vínculo com o vídeo fonte. |
| `pairs/*.npz` | Forward/backward e validade separados, metadados exatos por par. |
| `pair_index.json` | Vídeo, par, hash de fonte/configuração e SHA-256 do arquivo NPZ. |
| `selected_windows.csv` | Todas as chaves selecionadas da referência, antes dos pixels. |
| `histories.csv` | Centros dos 20 quadros disponíveis por janela, sem coordenadas futuras. |
| `features.csv` | 19 amostras por janela, validade, motivo de ausência e identidade do NPZ. |
| `window_coverage.csv` | Número de amostras válidas/inválidas por janela; nenhuma linha descartada. |
| `pair_metrics.csv` | Diagnósticos, denominadores e tempo por par. |
| `temporal_metrics.csv` | Mudança aparente entre campos consecutivos, 18 por vídeo. |
| `summary.json` | Cobertura e resumos descritivos dentro do vídeo. |

O manifesto raiz registra plano resolvido, fontes, pais auditados, orçamento,
recursos e hashes de todos os artefatos. O índice deve identificar exatamente
os 19 pares esperados de cada vídeo, sem duplicatas, ausências ou extras.
O consumidor não aceita vídeo vazio, chave como substituto do SHA-256, par
invertido, configuração divergente, shape/dtype incorretos ou campo futuro.
Confere os bytes antes de carregar NPZ com `allow_pickle=False` e cruza
metadados internos e externos. Não usa o cache legado.

## Validade, ausências e comparação futura

No Farnebäck denso, `valid` representa suporte numérico permitido e finito;
não é probabilidade de acerto nem certificado físico. A consistência FB é
relatada como diagnóstico, sem cortar vetores ou janelas por seu valor.
Uma amostra inválida mantém sua linha, coordenadas, par, `valid=false` e
motivo; u/v ficam vazios no CSV. Não substituir ausência por vetor zero.

Uma janela pode ter menos de 19 amostras válidas: isso é resultado de cobertura,
não falha operacional. Nenhuma janela é removida neste smoke. Corrupção,
par ausente ou erro de decodificação, por outro lado, fazem a run falhar; não
retirar o vídeo para declarar o restante completo. Antes de comparar preditores
com/sem fluxo será necessário registrar tratamento de ausências e coorte comum,
relatando a cobertura. O smoke não escolhe essa política a partir dos erros.

## Diagnósticos e interpretação

1. **Fotometria:** MAE entre I_s e I_(s+1)(p+F_s(p)), após cinza/255.
   Comparar também o MAE de deslocamento zero **nos mesmos pixels válidos**
   usados no warp. Registrar tamanho/fração do suporte. O domínio é intensidade
   normalizada, não pixels de posição. Variação de iluminação pode alterar o erro.
2. **Forward/backward:** norma de F_s(p)+B_s(p+F_s(p)), em pixels, com
   interpolação válida. Relatar média, suporte e fração ≤1,5px. Esse limiar
   é diagnóstico fixo e não seleciona candidatos ou amostras.
3. **Mudança temporal:** norma entre F_s(p) e F_(s+1)(p+F_s(p)), média e p95
   no suporte válido. Os 18 trios usam somente quadros0..19. Movimento real
   pode mudar; menor mudança não significa necessariamente melhor estimativa.
4. **Custo:** tempo de estimação dos dois sentidos e diagnósticos separado do
   custo total com verificação/decodificação/escrita; RSS amostrado e bytes.

Sem suporte, média/fração condicionada é nula com denominador zero, nunca
zero de erro artificial. Resumos por vídeo dão peso igual aos pares que têm
suporte e registram quantos contribuíram. Não somar pixels de vídeos diferentes
para apresentar significância. Não calcular p-valores, IC, ranking ou Pareto
com este smoke de uma configuração e dois vídeos.

Não existe GT de fluxo denso físico nesses vídeos; **não usar EPE real**.
Deslocamento do centro anotado tampouco é GT do movimento de cada pixel.
EPE só cabe em ensaios sintéticos com deslocamento conhecido. Não chamar
fluxo de velocidade do fluido ou inferir contracorrente a partir deste ensaio.

## Critérios de conclusão e orçamento

Antes de executar, aprovar testes sintéticos de temporalidade, interpolação,
ausência, corrupção e decodificação parcial; registrar código e plano em commit
com Git limpo. Limites: 900s de parede, 2.048MiB RSS amostrado, 512MiB de
artefatos. Verificar limites durante a execução; preservar falha/saídas parciais.
O teto de tempo é cooperativo entre operações, não interrupção de chamada nativa.

Concluir somente com 40 quadros, 38 pares de quadros e 76 campos (38 por
direção), 36 diagnósticos
temporais, todas as janelas selecionadas e suas 19 amostras reconciliadas,
hashes de entradas/saídas e estado do repositório reconferidos. Ausências
numéricas são preservadas, com contagens explícitas. Não exigir que uma métrica
melhore para chamar o smoke de concluído: conclusão é integridade da execução.

Depois, fazer conferência independente dos derivados: correspondências de
janela/história, amostragem, métricas, denominadores, cobertura, arquivos e
identidades. Coordenadas históricas, contagens e hashes devem coincidir
exatamente; amostras interpoladas e diagnósticos têm tolerância absoluta de
1e-9, fixada antes da execução. Recalcular a partir dos campos/quadros derivados
sem importar o código do projeto, repetir o estimador ou reler os vídeos.
Isso não é uma segunda decodificação independente do MP4 nem substitui
avaliação científica em vídeos completos.
Os resultados serão acrescentados em seção posterior, sem mudar este desenho.

## Fontes e próxima etapa

O contrato de imagem e os parâmetros usam a implementação local de
[Farnebäck](../../src/flow/classical/farneback.py), sua convenção em
[base.py](../../src/flow/base.py) e a documentação oficial de
[fluxo óptico](https://docs.opencv.org/4.13.0/d4/dee/tutorial_optical_flow.html)
e [calcOpticalFlowFarneback](https://docs.opencv.org/4.13.0/dc/d6b/group__video__track.html).
A convenção associa o vetor ao primeiro quadro. O método aproxima vizinhanças
por polinômios e usa pirâmides; o campo descreve movimento aparente da imagem.
As regras de causalidade, suporte e seleção acima são decisões prospectivas
deste projeto, não garantias fornecidas pela biblioteca.

Após o smoke conferido, registrar o estudo de características causais no treino
e a ablação com preditores equivalentes, mantendo os baselines e a referência
anteriores. Tracking/HOTA e avaliação fim a fim continuam com contratos próprios.
