# Continuidade experimental — plano executivo de 11/09/2026

## Direção e estado

Atualização de execução em 11/09: a orientação seguinte do pesquisador
priorizou testar os demais algoritmos, compará-los e validá-los antes de
escolher o componente da cadeia final de rastreamento e predição. A primeira
bateria concluída e conferida está descrita em
[Comparação de detectores estáticos v1](COMPARACAO_DETECTORES_CLASSICOS_V1.md):
43 configurações de seis famílias, incluindo T218 como referência, nos mesmos
576 quadros de treino, totalizando 24.768 avaliações. Smoke e busca passaram
pela conferência independente; refinamento, validação e YOLO têm etapas
próprias. Não há escolha antecipada do melhor detector.
Preparação do ambiente aprendido e contrato de tracking avançam em paralelo.
A ablação nos derivados abaixo permanece prevista; sua numeração registra
o roteiro anterior, não precedência obrigatória sobre esta comparação.

A próxima prioridade é produzir comparações reais que respondam aos objetivos
do TCC. Há código e infraestrutura suficientes para avançar; implementar mais
variantes ou repetir verificações encerradas não é pré-requisito para todas
as comparações. Este documento organiza a continuidade. Não substitui os
contratos executáveis de cada bateria. Os resultados da comparação clássica
estão no protocolo vinculado; a ablação com fluxo ainda não foi executada.

O marco mais recente de detecção é a busca comparativa de 11/09. Na frente
de fluxo, permanece o benchmark compacto 8a, conferido em 09/09. A primeira
avaliação real do preditor com fluxo ainda não ocorreu.
As evidências estão na [matriz](../projeto/MATRIZ_EXPERIMENTOS.md), no
[contrato compacto](FLUXO_COMPACTO_V1.md) e no [protocolo mestre](PROTOCOLO.md).

Em 11/09, o pesquisador informou que tempo de execução não deve limitar a
continuidade. O teto de 120 minutos do benchmark anterior permanece histórico:
a projeção de 134,21 minutos não passou naquela regra. Isso não invalida o
fluxo nem exige otimização de velocidade antes de qualquer nova comparação.
Novos protocolos poderão monitorar tempo sem esse corte, com limites de
memória, armazenamento, completude e falhas definidos antes da execução.
Não alterar o YAML, a run ou o verificador específico de 60 quadros do 8a.
Nova extração completa exige seu próprio executor e plano operacional.

## O que falta demonstrar

| Pergunta | Evidência que falta |
|---|---|
| O fluxo acrescenta informação útil à previsão? | Ablação causal pareada, primeiro com GT e depois com trajetórias estimadas |
| Qual rastreador preserva melhor as identidades? | Comparação real de HOTA, IDF1, MOTA, trocas de ID e fragmentações |
| Como um detector aprendido se compara ao clássico? | YOLO treinado/avaliado no protocolo atual versus T218 |
| Uma rede recorrente aproveita o fluxo? | LSTM sem/com fluxo com controle de entradas, treinamento e capacidade |
| Um fluxo aprendido muda o resultado? | Farnebäck versus RAFT sob suporte e preditor equivalentes |
| O resultado se mantém fora dos dados de escolha? | Avaliação externa com seleção e treinamento restritos aos dados permitidos |
| O sistema completo funciona em condições reais? | Propagação de erros, cobertura e previsões usando históricos estimados |

## 1. Primeira entrega: ablação exploratória nos derivados disponíveis

Usar as **mesmas 10.848 janelas dos 12 prefixos de treino** já conferidas no
8a. Não é necessário decodificar novamente vídeos ou repetir Farnebäck para
essa entrega. As últimas cinco amostras de todas essas janelas são válidas
no material registrado. Os prefixos não representam automaticamente vídeos
completos; o resultado será descritivo e exploratório, sem promoção ou teste
confirmatório da hipótese.

O resultado dos prefixos não será usado para eliminar o braço com fluxo,
redefinir a coorte ou escolher retrospectivamente novos parâmetros; a
ampliação prevista permanece independente do sinal observado.

As origens vão de 19 a 59. Imagens e pares de fluxo utilizados terminam até
59; alvos de avaliação podem chegar ao quadro 69 e serão lidos da referência
GT autenticada, sem abrir pixels futuros ou fornecê-los aos preditores.

Comparação principal: `cv_median5` versus `cv_median5_flow_last`. Como controle
secundário prospectivo, incluir velocidade pelo último deslocamento (`cv_last`),
com cálculo em float64, mesmas entradas e mesmos alvos. O fluxo medido na
cabeça pode aproximar o deslocamento da própria célula; esse controle ajuda
a interpretar se o híbrido apenas se aproxima de extrapolar o movimento mais
recente. Ele deve ser registrado antes de observar os erros. Persistência
pode constar como referência contextual nas mesmas janelas, sem substituir
o contraste principal. Não selecionar um vencedor nesta etapa.

Antes dos erros, registrar YAML e contrato próprios que fixem:

- hashes dos manifestos e QA do 8a e da referência individual;
- universo exato de janelas, métodos fixos e controle secundário;
- vinte posições históricas e dezenove pares disponíveis até a origem;
- elegibilidade comum pelas cinco amostras finais, com exclusões explícitas;
- ADE denso e FDE em H=1/5/10, em pixels;
- agregação por ID original dentro do vídeo e peso igual entre vídeos;
- saídas, tolerâncias, recursos, falhas e conferência independente.

O elo a implementar é um **leitor autenticado e um executor da ablação**.
O leitor deve conferir arquivos e chaves sem duplicatas, omissões ou extras,
ligar janela/amostra por vídeo, ID, segmento e par, e comparar coordenadas
amostradas com o histórico correto. Os preditores recebem somente históricos;
os alvos são entregues separadamente ao cálculo dos erros. Não reutilizar a
média dos baselines nas 343.776 janelas como controle desta coorte menor.
As previsões do braço mediana podem ser conferidas contra o subconjunto
correspondente da bateria anterior, sem repetir essa bateria.

Entrega: previsões e métricas por janela, tabelas por ID/vídeo, diferenças
pareadas, cobertura, exclusões, custo e exemplos identificados de ganho e
piora. Encerrar o marco quando a comparação estiver executada e conferida,
mesmo que o fluxo não melhore o erro. Testes novos devem cobrir os riscos do
novo elo; não repetir experimentos encerrados ou criar uma nova campanha de
otimização como condição para esta entrega.

## 2. Rastreamento real, em paralelo à frente de predição

Fechar o contrato de avaliação antes da primeira bateria: indivíduos 0/2,
clusters, lacunas, IDs, quadros vazios, caixas previstas sem observação e
convenção geométrica. A tolerância de centros de 10 px da detecção não define
automaticamente a similaridade do HOTA. Usar a implementação de referência
[TrackEval](https://github.com/JonathonLuiten/TrackEval), que oferece HOTA,
métricas CLEAR e métricas de identidade, com versão fixada e adaptação
documentada do dataset.

Primeiro comparar centroide guloso, Húngaro e SORT nos treinos, com caixas GT
sem fornecer IDs ao rastreador, e depois com T218. O cenário GT isola a
associação; não demonstra resistência a detecções perdidas. Incluir
ByteTrack-style como implementação local em duas etapas, com limitações
explícitas. Scores constantes de GT/threshold não exercitam a recuperação
por baixa confiança como scores informativos de YOLO. Sua comparação
principal deverá incluir o detector aprendido. Adaptive Flow-SORT entra como
ablação do uso de fluxo na associação, com entrada causal própria; o cache
amostrado em centros GT da predição não é automaticamente seu cache de tracking.

Não chamar a variante local de reprodução integral do
[ByteTrack oficial](https://github.com/FoundationVision/ByteTrack).
Se a comparação acadêmica requerer a implementação oficial, integrá-la e
identificá-la separadamente, sem renomear resultados locais.

Entrega: HOTA/IDF1/MOTA e cobertura por vídeo, eventos de identidade e
visualizações de cruzamentos, perdas e reencontros. Escolha de parâmetros no
treino; seleção registrada na validação antes de congelar. Não usar GT para
corrigir IDs durante a execução real ou reconstruir artificialmente históricos.

## 3. Ambiente aprendido, detector e previsão recorrente

Inspeção somente leitura em 11/09: `nvidia-smi` detectou RTX 4070 Ti com
12.282 MiB de memória total reportada. A `.venv` clássica não tem distribuições
PyTorch, torchvision ou Ultralytics instaladas. Isso identifica preparação
necessária, não ausência de GPU ou inviabilidade dos modelos. Ainda não foi
testada inferência real ou compatibilidade CUDA nesta retomada.

Preparar ambiente aprendido reproduzível preservando a referência CPU.
Conferir importações, GPU, pesos e uma execução curta real antes de treinar.
Depois treinar YOLO apenas nas divisões permitidas e compará-lo ao T218 sob
o mesmo contrato v3. Fixar entrada/saída, pré-processamento, seleção, sementes
e condições de avaliação. Não promover o piloto histórico como resultado atual.

Comparar LSTM sem/com fluxo com mesmas janelas, alvos, divisões e processo de
seleção. Registrar o número de parâmetros: acrescentar canais pode aumentar
a capacidade. Uma proposta de controle é manter arquitetura e canais iguais,
substituindo o fluxo por zero no braço de controle; distinguir essa ablação
da LSTM que originalmente só possui posições/velocidades. Normalização e
aplicação desse controle devem ser fixadas antes da execução: o controle
recebe valores constantes independentes do fluxo observado naquela janela.
As estatísticas de normalização não podem depender de validação ou teste. O
treinamento pertence somente ao treino correspondente; seeds 42/123/2026
são agregadas dentro de vídeo, não tratadas como novos vídeos.

RAFT deve ser avaliado como representante aprendido de fluxo após validar
ambiente, pesos e recursos. Primeiro comparar sob a mesma amostragem e
preditor; depois investigar interações previstas no desenho. Não introduzir
máscaras, compensação global e novos horizontes todos de uma vez, pois isso
impediria atribuir uma diferença ao componente alterado.

## 4. Ampliar a extração e avaliar a cadeia completa

Para vídeos completos, registrar processamento por vídeo/lotes e descarte
de estruturas, índices, retenção, sentinelas e recuperação de falhas.
A memória do prefixo não certifica a memória completa. Instrumentação breve
serve ao monitoramento; otimização de velocidade é uma escolha operacional,
não condição científica imposta pelos 120 minutos históricos.

Repetir os contrastes planejados na coorte ampliada comum, contabilizando
faltas de fluxo e janelas sem futuro completo. Não substituir ausências por
zero nem comparar métodos em populações diferentes sem identificá-las.

Avaliar predição com trajetórias estimadas por detector+rastreador. Definir
antes da execução como uma trajetória estimada será ligada à referência
para medir erro, preservando trocas de ID, lacunas e perdas. Relatar cobertura
junto ao ADE/FDE: perder casos difíceis pode reduzir o erro médio entre os
casos restantes sem melhorar o sistema completo.

O núcleo prioritário é T218/YOLO; centroide/Húngaro/SORT/ByteTrack-style;
Farnebäck/RAFT; persistência/CV/CV+fluxo/LSTM sem e com fluxo. Kalman de
predição e Adaptive Flow-SORT são extensões coerentes. O restante do catálogo
continua disponível, sem necessidade de testar todo produto cartesiano antes
de responder às perguntas centrais. Isso é ordem de execução, não exclusão
silenciosa de compromissos acadêmicos.

## 5. Avaliação externa e encerramento acadêmico

Projetar desde já, antes de abrir teste/folds, a seleção e o treinamento em
cada divisão. A avaliação externa não pode reutilizar como independentes as
escolhas informadas pelo vídeo avaliado. Cinco grupos por si só não resolvem
[viés de seleção](https://www.jmlr.org/papers/v11/cawley10a.html).
Preservar o bloqueio atual e declarar a exposição histórica dos vídeos de
teste. A decisão confirmatória final precisa ser alinhada ao orientador;
isso não impede o desenvolvimento nos treinos agora.

H=10 corresponde a aproximadamente 0,20 s nos vídeos desta coleção. Manter
o contrato atual para a primeira comparação e restringir suas conclusões à
predição curta. Horizontes maiores exigem proposta prospectiva própria.

Concluir com comparações reais clássicas/aprendidas, identidades avaliadas,
ablação em GT e cadeia estimada, cobertura, resultados por vídeo, custos,
incerteza compatível com o desenho, exemplos de falha e discussão acadêmica.
Aplicação nos 65 vídeos sem tracking manual é qualitativa; não fornece
acurácia de trajetória sem referência. Um resultado sem benefício do fluxo
é uma conclusão válida se os controles e limitações estiverem claros.

Atualizar documentação e monografia a cada entrega experimental, com testes
proporcionais aos riscos das mudanças. Preservar fontes e runs encerradas.
HTMLs e guias locais continuam fora dos commits.
