# Protocolo experimental mestre

Este documento transforma o plano do TCC em uma fila de execução. O teste pode
ser rodado pelo pesquisador em outra sessão; código, configuração e teste
sintético precisam existir antes de uma bateria longa.

## Regra comum de promoção

Para cada algoritmo:

1. validar a implementação com caso sintético e smoke test;
2. fazer busca grossa exclusivamente no treino;
3. refinar as cinco melhores configurações;
4. rodar as duas finalistas nos quatro vídeos completos de validação;
5. escolher uma por métrica primária, desempatar por recall, latência e memória;
6. congelar parâmetros e hash da configuração;
7. executar uma única vez no teste bloqueado;
8. confirmar a configuração congelada em previsões fora da amostra de 5 folds;
9. fechar a ficha individual e incorporar o resultado na monografia.

As seeds de modelos estocásticos são `42`, `123` e `2026`. Buscas em massa
geram métricas e previsões, não MP4. MP4 é produzido nos quatro vídeos de teste
e em poucos casos típicos ou de falha.

### Guardas executáveis

- `split=test` é aceito exclusivamente com `stage=test`, `frozen=true` e um
  YAML existente dentro de `configs/frozen/`;
- os folds A-E são aceitos exclusivamente com configuração congelada e etapa
  `oof`, `five_fold` ou `cross_validation`;
- `search`, `refine` e `validation` nunca aceitam um fold como split;
- o alias `all`, por incluir o teste, só existe para `stage=final` com uma
  configuração congelada; a confirmação 5-fold sempre roda A-E separadamente;
- `stage=application` e `split=application` formam um par inseparável e também
  exigem configuração congelada;
- uma run congelada recusa overrides de algoritmo, parâmetros, métrica e
  amostragem. Stage, split, seed, vídeo e renderização continuam operacionais;
- quando o executor recebe um split/fold nomeado, o ID real obtido do vídeo,
  `detections.csv`, `tracks.csv` ou cache é conferido contra
  `configs/protocol/splits.yaml` antes do processamento pesado.

### Limitação do holdout recuperado

Antes deste protocolo, a exploração frame a frame usou três frames dos 20
vídeos, incluindo `24, 38, 47, 54` (30 summaries por vídeo na árvore
histórica). Esses quatro vídeos não são, portanto, um holdout totalmente cego.
As 120 observações permanecem marcadas como legado e não são usadas para a
seleção retomada. A execução completa confirmatória continua única e só pode
ocorrer após congelamento; a confirmação 5-fold é obrigatória para reduzir a
dependência desse holdout previamente visto.

## Fila 0 — infraestrutura

- [x] Proteger a fonte LaTeX em `monografia/`.
- [x] Registrar split 12/4/4, cinco folds, seeds e manifesto dos 20 vídeos.
- [x] Validar disjunção dos splits e cobertura dos folds.
- [x] Fechar testes do alinhamento de GT por número de frame.
- [x] Fechar executor com `--config`, `--set`, `--split`, `--stage`, `--seed`.
- [x] Fechar tabelas SQLite de runs, métricas por frame/vídeo e custos.
- [x] Rodar toda a suíte curta antes de qualquer bateria.

Critério: ambiente reproduzível, monografia protegida, splits sem vazamento e
testes sintéticos verdes.

Fila 0 fechada em 2026-08-29 para o núcleo clássico/CPU. A validação específica
de PyTorch/CUDA para YOLO, RAFT e LSTM permanece antes das baterias neurais e
não deve ser confundida com a validação estrutural já concluída.

## Fila 1 — detecção

Unidade de triagem: frame para threshold/Otsu/adaptativo/Blob/Watershed/YOLO;
clipe com aquecimento para MOG2/KNN.

Ordem de fechamento:

1. threshold fixo + morfologia (`T200/o1/c2` e `T190/o1/c1` obrigatórios);
2. Otsu;
3. threshold adaptativo;
4. híbrido de normalização local + realce morfológico + segmentação;
5. Blob;
6. MOG2;
7. KNN;
8. Watershed;
9. YOLO com early stopping e três seeds.

Métrica de promoção: F1 binário com matching Húngaro e gate de centro de 15 px.
Complementares: gates 10/20 px, precision, recall, erro de centro, count MAE,
bias, latência, RAM/VRAM; mAP e três classes são secundários no YOLO.

Saída: um vencedor congelado por método e dois detectores na fronteira de Pareto
(melhor qualidade e melhor eficiência).

## Fila 2 — tracking

Cada tracker roda em dois cenários: boxes GT (associação isolada) e boxes do
detector congelado (fim a fim).

1. centroide guloso;
2. associação Húngara;
3. SORT (Kalman + Húngaro);
4. ByteTrack, principalmente com scores do YOLO;
5. híbrido adaptativo com movimento/fluxo, comparado separadamente.

Promoção: HOTA; complementares IDF1, MOTA, ID switches, fragmentações, track
recall, mediana/p95 de tempo por frame e memória. O adaptador TrackEval está
pronto; a dependência e a avaliação oficial ainda precisam ser executadas.

## Fila 3 — movimento aparente

1. Lucas–Kanade esparso;
2. Farneback denso;
3. Horn–Schunck denso e suave;
4. RAFT opcional;
5. híbrido robusto CPU (compensação global/consistência + estimador local);
6. o mesmo híbrido com refino RAFT, como variante neural separada.

Avaliação: erro fotométrico pós-warp, consistência forward/backward, estabilidade
temporal e latência. EPE só em sequências sintéticas com deslocamento conhecido.
Ao estimar fundo, células/artefatos são mascarados. Features cacheadas por ponto:
`flow_u`, `flow_v`, magnitude e direção.

O handoff também é parte da ablação: as caixas dos dois frames podem mascarar
células/artefatos na estimação, e o cache é associado às tracks por amostragem
direta ou por anel de fundo. Medida ausente permanece inválida, nunca é
codificada como vetor zero.

## Fila 4 — predição

Histórico padrão de 20 frames; horizontes 1, 5 e 10. Primeiro trajetórias GT,
depois trajetórias do tracker. O split é sempre por vídeo.

1. persistência;
2. velocidade constante;
3. Kalman;
4. filtro de partículas;
5. LSTM sem fluxo;
6. LSTM com fluxo;
7. híbrido cinemático/fluxo, se distinto das ablações acima.

Promoção: ADE e FDE, com erro por horizonte, duração de trajetória e densidade.
A ablação LSTM usa exatamente dados, arquitetura, seeds e hiperparâmetros iguais;
somente as features de fluxo mudam.

## Fila 5 — estatística e aplicação

- Agregar primeiro por frame/trajetória e depois por vídeo.
- Três ou mais métodos: Friedman e Wilcoxon pareado pós-hoc com Holm.
- Dois métodos: Wilcoxon pareado.
- Reportar diferença pareada, efeito e IC95 por bootstrap agrupado por vídeo.
- Construir fronteiras de Pareto sem placar único subjetivo.
- Medir qualidade, mediana/p95/FPS/memória, treino, tamanho, esforço registrado,
  dependências, labels e necessidade de GPU/calibração.
- Retreinar modelos aprendidos nos 20 anotados com hiperparâmetros congelados.
- Executar os dois representantes nos 65 sem tracking e exportar tabelas/caches.
- Nesses 65, relatar aplicação e estabilidade; não acurácia contra ground truth.

## Critérios de aceitação antes de dizer “concluído”

- matching sintético tem TP/FP/FN conhecidos e associação um-para-um;
- labels ausentes não viram frames negativos;
- MOG2/KNN reiniciam por vídeo e excluem aquecimento;
- tracking cobre cruzamento, desaparecimento e nascimento sintéticos;
- fluxo recupera translação sintética dentro da tolerância;
- janelas não atravessam splits, IDs nem lacunas;
- ADE/FDE batem com exemplos analíticos;
- cada run guarda config resolvida, seed, commit, ambiente, status e custo;
- nenhuma execução sobrescreve outra;
- conjunto de teste só é usado depois do congelamento.
