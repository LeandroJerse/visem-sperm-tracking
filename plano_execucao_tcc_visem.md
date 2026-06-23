# Plano de execução do TCC com VISEM e VISEM-Tracking

## 1. Diagnóstico dos materiais

### Datasets principais

**VISEM-Tracking** deve ser o dataset central do TCC. Ele possui 20 vídeos anotados de 30 segundos, 29.196 frames, bounding boxes manuais, IDs de tracking e três classes: espermatozoide normal, cluster e small/pinhead. Como as anotações estão em formato YOLO e incluem IDs persistentes, ele permite estudar detecção, rastreamento multiobjeto, extração de trajetórias, métricas de tracking e predição de trajetória.

**VISEM original** deve ser usado como contexto e expansão. Ele possui 85 participantes, vídeos de 640 x 480 a 50 FPS, duração de 2 a 7 minutos, dados de análise seminal, hormônios, ácidos graxos e dados de participante. Ele é importante para contextualizar CASA e fertilidade masculina, mas não possui as anotações de tracking necessárias para treinar e avaliar diretamente rastreadores supervisionados.

### Lacuna importante

O tema do TCC inclui estimar o campo de fluxo/corrente contrária gerado por um tubo. Os datasets VISEM e VISEM-Tracking são altamente relevantes para espermatozoides em vídeo, mas não parecem conter ground truth explícito do campo de fluido nem um experimento com tubo/corrente contrária. Portanto, o módulo de fluxo deve ser tratado como estimativa visual/proxy, usando optical flow e análise das trajetórias, não como tarefa supervisionada com rótulo real de velocidade do fluido.

### Caminho mais viável

O caminho seguro é transformar o TCC em uma pipeline modular:

1. Detecção dos espermatozoides nos frames.
2. Tracking multiobjeto com IDs persistentes.
3. Extração de trajetórias e métricas cinemáticas.
4. Estimativa de fluxo/movimento global ou local por optical flow.
5. Predição de posições futuras usando histórico da trajetória e vetor de fluxo estimado.

O foco científico deve ser: "avaliar se a incorporação de informação de fluxo óptico melhora o rastreamento e/ou a predição de trajetórias de espermatozoides em vídeos microscópicos".

## 2. Resumo técnico do problema

Em CASA, a análise de sêmen busca medir concentração, motilidade, morfologia e padrões cinemáticos dos espermatozoides. A análise manual é trabalhosa, subjetiva e difícil de reproduzir, principalmente porque os espermatozoides são pequenos, têm baixo contraste, movimento rápido e podem se cruzar, sair de foco ou formar clusters.

Computacionalmente, o TCC pode ser formulado como um problema de vídeo:

- cada frame contém múltiplos objetos pequenos;
- cada objeto precisa ser detectado por centroide ou bounding box;
- deteções entre frames precisam ser associadas ao mesmo ID;
- a sequência de posições forma uma trajetória;
- o optical flow fornece uma aproximação do movimento aparente no campo visual;
- um modelo de predição usa trajetória passada e fluxo local para prever posições futuras.

## 3. Rotina de estudo

### Semana típica

- Segunda: leitura teórica e resumo de artigo.
- Terça: implementação pequena e controlada.
- Quarta: experimento em 1 ou 2 vídeos.
- Quinta: métricas, gráficos e análise de erro.
- Sexta: escrita de 1 a 2 páginas da monografia.
- Sábado: revisão, organização de código e backlog.
- Domingo: descanso ou leitura leve.

### Ordem de estudo

1. OpenCV, leitura de vídeo, grayscale, thresholding, morfologia e blobs.
2. Formato YOLO, conversão de bounding boxes e visualização de anotações.
3. Kalman Filter, Hungarian matching, IoU e SORT.
4. Métricas MOT: MOTA, MOTP, IDF1, HOTA, fragmentações e ID switches.
5. Optical flow: Lucas-Kanade, Farneback, visualização HSV/quiver e separação entre movimento dos espermatozoides e movimento global.
6. Predição: baseline por velocidade constante, Kalman, LSTM/GRU simples.
7. Evoluções modernas: YOLOv5/YOLOv8, ByteTrack, RAFT, modelos sequenciais com features de fluxo.

### Exercícios práticos

- Abrir um vídeo do VISEM-Tracking e renderizar as anotações.
- Converter YOLO para `(frame, id, class, x1, y1, x2, y2, cx, cy)`.
- Gerar um JSON/CSV único de trajetórias.
- Implementar baseline de tracking por nearest centroid.
- Implementar SORT com Kalman + Hungarian.
- Calcular VCL, VSL, VAP e LIN por trajetória.
- Rodar Farneback e extrair o vetor de fluxo no centroide de cada espermatozoide.
- Comparar predição por velocidade constante, Kalman e LSTM pequena.

## 4. Plano de execução por fases

### Fase 1: Organização e leitura dos dados

Objetivo: entender o dataset e criar base reprodutível.

Tarefas:
- baixar VISEM-Tracking;
- mapear estrutura de pastas;
- criar script de conversão de anotações;
- separar treino/validação/teste respeitando vídeos inteiros;
- criar visualizador de frames com boxes e IDs.

Entregáveis:
- `data/processed/tracks.csv`;
- notebook de inspeção;
- vídeo curto anotado.

Critério de conclusão:
- conseguir escolher qualquer vídeo e visualizar boxes, classes e IDs corretamente.

### Fase 2: Baselines de detecção e tracking

Objetivo: ter uma pipeline clássica funcional.

Tarefas:
- baseline de detecção por thresholding/morfologia;
- baseline usando as boxes ground truth como "detector perfeito";
- tracker por nearest centroid;
- SORT com Kalman + Hungarian;
- avaliação com MOTA, IDF1 e HOTA.

Entregáveis:
- tabela de métricas por vídeo;
- vídeos anotados com IDs;
- análise dos principais erros.

Critério de conclusão:
- pipeline executa do frame 0 ao último frame e exporta trajetórias avaliáveis.

### Fase 3: Fluxo óptico e campo de movimento

Objetivo: estimar informação de movimento visual útil para tracking/predição.

Tarefas:
- rodar Farneback entre frames consecutivos;
- visualizar fluxo por HSV e quiver;
- amostrar o vetor de fluxo no centroide de cada box;
- testar filtros: mediana espacial, média local e máscara fora dos espermatozoides;
- estimar movimento global do fundo quando aplicável.

Entregáveis:
- mapas de fluxo;
- features por ponto: `flow_u`, `flow_v`, magnitude e direção;
- comparação entre velocidade observada da trajetória e vetor de optical flow.

Critério de conclusão:
- cada ponto de trajetória possui features de fluxo associadas.

### Fase 4: Predição de trajetória

Objetivo: prever posições futuras usando histórico e fluxo.

Tarefas:
- montar janelas temporais, por exemplo 10 frames de entrada e 5 frames futuros;
- baseline 1: última posição;
- baseline 2: velocidade constante;
- baseline 3: Kalman;
- modelo moderno mínimo: LSTM/GRU com entrada `(x, y, dx, dy, flow_u, flow_v)`;
- avaliar ADE e FDE.

Entregáveis:
- dataset de janelas;
- tabela ADE/FDE;
- gráficos de trajetória real vs. prevista.

Critério de conclusão:
- mostrar se o fluxo melhora, piora ou não altera a predição.

### Fase 5: Evoluções modernas opcionais

Objetivo: melhorar resultados se houver tempo.

Opções:
- treinar YOLOv5/YOLOv8 no VISEM-Tracking;
- usar ByteTrack com boxes do detector treinado;
- testar RAFT para optical flow;
- testar Transformer temporal pequeno;
- usar pseudo-labels nos vídeos não anotados.

Critério de uso:
- só avançar para essas opções depois que as fases 1 a 4 estiverem fechadas.

## 5. Metodologia recomendada

### Baseline obrigatório

- Dataset: VISEM-Tracking.
- Entrada: frames e anotações YOLO com IDs.
- Detecção: usar ground truth como detector perfeito para isolar o problema de tracking; depois testar detector clássico.
- Tracking: nearest centroid e SORT.
- Fluxo: Farneback.
- Predição: velocidade constante e Kalman.
- Métricas: MOTA, IDF1, HOTA, ADE e FDE.

### Contribuição principal realista

Comparar modelos de predição com e sem features de fluxo:

- sem fluxo: `(x, y, dx, dy)`;
- com fluxo: `(x, y, dx, dy, flow_u, flow_v, flow_mag, flow_angle)`.

Essa contribuição é viável porque não depende de treinar um detector pesado e conversa diretamente com o tema do TCC.

### Contribuições extras

- YOLO + ByteTrack para pipeline fim a fim.
- RAFT vs. Farneback para fluxo.
- Métricas CASA por trajetória: VCL, VSL, VAP, LIN.
- Classificação de motilidade a partir das trajetórias.

## 6. Experimentos

### Experimento A: detecção

Comparar:
- thresholding/morfologia;
- YOLOv5/YOLOv8, se houver tempo;
- ground truth como limite superior.

Métricas:
- precision, recall, F1, mAP@0.5.

### Experimento B: tracking

Comparar:
- nearest centroid;
- SORT;
- ByteTrack, se houver detector treinado.

Métricas:
- HOTA como métrica principal;
- MOTA, IDF1, ID switches, fragmentações e tempo por frame.

### Experimento C: fluxo óptico

Comparar:
- Farneback;
- Lucas-Kanade em pontos detectados;
- RAFT, se houver GPU/tempo.

Métricas e análises:
- consistência visual;
- correlação entre vetor de fluxo e deslocamento real;
- comparação de magnitude/direção por região do frame.

### Experimento D: predição

Comparar:
- última posição;
- velocidade constante;
- Kalman;
- LSTM/GRU sem fluxo;
- LSTM/GRU com fluxo.

Métricas:
- ADE;
- FDE;
- erro por horizonte temporal;
- erro por velocidade do espermatozoide.

### Tabelas e figuras para o TCC

- Tabela dos datasets e características.
- Diagrama da pipeline.
- Exemplos de frames com boxes e IDs.
- Visualização do optical flow.
- Tabela de métricas de tracking.
- Tabela ADE/FDE de predição.
- Gráficos de trajetórias reais vs. previstas.
- Curvas de erro por horizonte.

## 7. Cronograma de 16 semanas

### Semanas 1 e 2: leitura e dataset

- Ler VISEM, VISEM-Tracking e artigos de CASA/rheotaxis.
- Baixar e organizar VISEM-Tracking.
- Criar conversor de anotações e visualizador.

### Semanas 3 e 4: baselines visuais

- Implementar detecção simples.
- Criar CSV de trajetórias com ground truth.
- Gerar vídeos anotados.

### Semanas 5 e 6: tracking clássico

- Implementar nearest centroid e SORT.
- Rodar avaliação por vídeo.
- Escrever seção de tracking clássico.

### Semanas 7 e 8: optical flow

- Implementar Farneback.
- Extrair features de fluxo por trajetória.
- Escrever seção de fluxo óptico.

### Semanas 9 e 10: predição clássica

- Criar janelas temporais.
- Avaliar última posição, velocidade constante e Kalman.
- Gerar gráficos ADE/FDE.

### Semanas 11 e 12: predição neural simples

- Treinar LSTM/GRU pequena.
- Comparar com e sem fluxo.
- Consolidar resultados.

### Semanas 13 e 14: extras controlados

- Tentar YOLO/ByteTrack ou RAFT, dependendo de tempo e hardware.
- Se os extras atrasarem, cortar sem prejudicar o TCC.

### Semanas 15 e 16: escrita e revisão

- Finalizar capítulos.
- Revisar figuras, tabelas e metodologia.
- Rodar experimentos finais com seeds/configs fixos.

## 8. Estrutura da monografia

1. **Introdução**
   - Problema de fertilidade masculina, CASA e motivação para análise automática.
   - Objetivo geral e objetivos específicos.

2. **Fundamentação teórica**
   - Visão computacional em vídeos microscópicos.
   - Detecção, tracking multiobjeto, optical flow e predição de trajetórias.
   - Métricas CASA: VCL, VSL, VAP e LIN.

3. **Trabalhos relacionados**
   - VISEM como dataset multimodal.
   - VISEM-Tracking como dataset anotado para tracking.
   - SORT, ByteTrack, RAFT e modelos de predição.

4. **Materiais e métodos**
   - Descrição do dataset.
   - Pipeline proposta.
   - Conversão de anotações.
   - Métodos de detecção, tracking, fluxo e predição.

5. **Experimentos**
   - Protocolo de treino/validação/teste.
   - Métricas.
   - Configurações.

6. **Resultados e discussão**
   - Tracking.
   - Fluxo óptico.
   - Predição com e sem fluxo.
   - Limitações.

7. **Conclusão**
   - Resumo dos achados.
   - O que funcionou.
   - Trabalhos futuros: dados com corrente real, RAFT, modelos 3D, microfluídica.

## 9. Desafios e mitigação

- Objetos pequenos e baixo contraste: começar usando ground truth, depois detector simples.
- Clusters e pinheads: avaliar separado por classe e talvez focar inicialmente em espermatozoides normais.
- Cruzamentos e trocas de ID: usar HOTA/IDF1 e analisar vídeos com maior densidade.
- Fluxo óptico captura movimento dos espermatozoides, não necessariamente do fluido: declarar como "movimento aparente estimado" e usar máscaras/filtros.
- Falta de ground truth de corrente: não prometer medição física do fluido; prometer estimativa visual e uso como feature.
- Deep learning pode consumir tempo: deixar YOLO, RAFT e Transformer como extras.
- Dataset grande: começar com 4 a 6 vídeos e só depois escalar.

## 10. Primeiras tarefas dos próximos 7 dias

1. Ler os PDFs `VISEM_Dataset.pdf` e `VISEM_Tracking.pdf` e produzir fichamento de 1 página para cada um.
2. Baixar `VISEM-Tracking.zip` do Zenodo.
3. Inspecionar a estrutura de pastas e listar vídeos, frames, labels e labels com tracking IDs.
4. Criar script para converter YOLO tracking labels em CSV único.
5. Renderizar 100 frames de um vídeo com boxes, classes e IDs.
6. Criar um notebook com estatísticas: número de frames, boxes por frame, duração das trajetórias e distribuição por classe.
7. Escrever o rascunho da introdução com: problema, motivação, objetivo geral e objetivos específicos.

## Fontes principais

- VISEM no Zenodo: https://zenodo.org/records/2640506
- VISEM-Tracking no Zenodo: https://zenodo.org/records/7293726
- Artigo VISEM-Tracking: https://www.nature.com/articles/s41597-023-02173-4
- Repositório oficial VISEM-Tracking: https://github.com/simulamet-host/visem-tracking
- Página Simula do VISEM: https://www.simula.no/research/visem-multimodal-video-dataset-human-spermatozoa
- RAFT: https://arxiv.org/abs/2003.12039
- SORT: https://arxiv.org/abs/1602.00763
- DeepSORT: https://arxiv.org/abs/1703.07402
- ByteTrack: https://arxiv.org/abs/2110.06864
- HOTA: https://link.springer.com/article/10.1007/s11263-020-01375-2
