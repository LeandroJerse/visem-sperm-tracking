# Próximo treino YOLO — proposta para registro prospectivo

Nota de 11/09/2026. **Proposta, sem treinamento executado ou pesos baixados.**
Não substitui um YAML/contrato aprovado e implementado.

## Já registrado e conferido

O ambiente usa Python 3.13.3, torch 2.9.1+cu128, torchvision 0.24.1+cu128 e
Ultralytics 8.4.147, com versões completas em `requirements-ml.lock`. CUDA
passou em verificações sintéticas na RTX 4070 Ti; isso não certifica um batch
de treinamento.

O dataset de `ca68f16` contém 17.466 quadros anotados dos 12 treinos e 5.850
dos quatro vídeos de validação. As 174 lacunas do vídeo 23 estão excluídas.
A QA independente confirmou 23.316 pares, hashes fonte/cópia e igualdade
exata das caixas YOLO/FTID. Manifesto SHA256
`e13f65035d1ae90dcb2337a8942022d70a45cfbb926a611df21b83add2c8bf42`;
QA `0ad645d9cd20825984b70d5dab2b6d5dfd1a36970e10bd2a8b0129f81b2490be`.
O derivado está selado. Nenhum modelo foi promovido por essa preparação.

Bases locais: `docs/metodologia/AMBIENTE_APRENDIDO_V1.md`,
`DATASET_YOLO_V1.md`, `CLASSES_E_AGRUPAMENTOS.md` e
`RASTREAMENTO_COMPARACAO_V1.md`; código em `src/detection/yolo_dataset.py`,
`yolo_training.py`, `yolo_evaluation.py` e `learned/yolo.py`.

## Primeiro protocolo executável proposto

1. Implementar executor novo, com schema fechado e registro dos argumentos
   efetivamente enviados à biblioteca. Testar sinteticamente bloqueios de
   split, hashes, caches, checkpoints e falhas. `_training_kwargs` histórico
   não repassa todas as opções aceitas pelo resolvedor: ainda não serve como
   garantia desse protocolo.
2. Criar clone independente do derivado dentro de cada run consumidora;
   autenticar manifesto/QA e cada JPEG/label, gerar novo descritor só train/val
   e reautenticar depois. Sem hardlinks ou reparos silenciosos. Mesmo
   `cache=False` permite `labels.cache`: todos os caches ficam no consumidor,
   nunca nas fontes ou no derivado selado. Materializar novamente as fontes
   não é necessário.
3. Fazer smoke de engenharia com subamostra determinística dos treinos
   11/12, uma época, sem seleção científica. Registrar separadamente os
   quadros de ajuste e conferência internos ao smoke. Não abrir os quatro
   vídeos oficiais de validação para decidir batch, precisão ou viabilidade.
4. Depois do smoke, registrar receita completa, orçamento e critérios de
   seleção antes de executar as três seeds oficiais 42/123/2026. Todas as
   seeds usam a mesma receita e coorte; nunca selecionar a seed mais favorável.

| Decisão proposta | Valor inicial ou registro necessário |
|---|---|
| Arquitetura | YOLOv8n, detecção de três classes; proposta inicial compatível com o código existente, ainda não escolha final |
| Inicialização | Pesos COCO oficiais de origem/versão e SHA256 autenticados; inventariar pesos já locais antes de qualquer download; nenhum checkpoint de piloto VISEM |
| Resolução | Primeiro candidato 640; 960 somente como segunda receita prospectiva, com seu próprio custo, sem alteração após ler validação |
| Batch/execução | Smoke começa em batch fixo 8, GPU 0, workers 0, cache=False; após conferir recursos, congelar valores para todas as seeds; evitar batch automático −1 |
| Precisão | Começar smoke com AMP desligado para evitar verificação com download implícito; liberar AMP somente após teste próprio de finitude, recursos e pesos auxiliares registrados |
| Otimização | Declarar otimizador, lr inicial/final, scheduler, warmup, momentum/betas, weight decay, acumulação e perdas box/cls/dfl; não deixar `optimizer=auto` mudar a receita sem registro |
| Augmentations | Explicitar flips, rotação, escala, translação, HSV, mosaic, mixup, copy-paste e época de desativação; proposta inicial conservadora: sem mosaic/mixup/copy-paste, sem alteração de matiz/saturação; valores restantes precisam ser fixados |
| Épocas/checkpoint | Proposta: orçamento fixo de 100 épocas, sem early stopping, `last.pt` da época 100 como modelo principal; falha antes disso é run incompleta, não um checkpoint final válido |

Guardar `best.pt` e `last.pt`, SHA256, época real, pesos EMA e estado de
otimizador quando disponível. Na versão instalada, `best.pt` usa mAP50–95
nativo: não é “melhor F1 de centros”. A proposta de época fixa evita escolher
época usando a validação; mAP nativo pode ser diagnóstico, sem comandar essa
escolha. Se for adotado early stopping/best.pt, registrar explicitamente a
validação como conjunto de seleção de época, sem chamar seu resultado de
estimativa independente. Retomada completa de otimizador/scheduler ainda
precisa de contrato; carregar `last.pt` como modelo em nova run não a garante.

## Comparação justa e dados de avaliação

Treinar nos JPEGs fornecidos não prova igualdade de pixels com os MP4s.
Para comparar detectores, avaliar YOLO sobre **os mesmos arrays BGR
autenticados derivados dos MP4s** usados pelos clássicos: primeiro os 576
quadros de treino; depois a validação completa sob executor próprio.
Para validação, fixar decoder/versão e cache de pixels canônicos ou provar
equivalência da decodificação. Não comparar F1 de JPEG de um método com F1
de MP4 de outro como se a entrada fosse idêntica. Letterbox/redimensionamento
interno do YOLO deve ser registrado; caixas voltam às coordenadas originais
640×480. A QA atual certifica JPEGs e anotações, não essa equivalência MP4.

Selecionar confiança/NMS somente no treino, com grade prospectiva. Aplicar
v3: indivíduos GT 0/2, matching a 10 px, sensibilidades 15/20, proteção dos
indivíduos antes de ignorar resíduos em clusters e todas as classes previstas
preservadas. Agregar seeds dentro de cada vídeo e depois vídeos com igual
peso; 576 quadros e três seeds não viram réplicas independentes. mAP
class-aware é complementar. Validação escolhe finalistas/configuração; teste
24/38/47/54 permanece bloqueado, com exposição histórica declarada.

Para ByteTrack-style, exportar scores contínuos com piso ≤ menor limiar baixo
que venha a ser registrado. A grade histórica chega a 0,05; proposta de piso
0,01 preservaria essa faixa, mas ainda exige contrato. Fixar NMS, `max_det`,
precisão e política de classes; detectar saturação do limite no treino.
Caixas eliminadas por corte/NMS não podem ser recuperadas pelo rastreador.
O wrapper atual não explicita todos esses argumentos e precisa ser ampliado.

## Recursos e saída da próxima etapa

Orçamento de treino continua pendente: medir VRAM alocada/reservada, memória
do processo/filhos e disco no smoke; projetar três clones, caches, checkpoints
e saídas antes da bateria. O teto de 1 GiB/2 GiB do preparo do dataset não se
aplica automaticamente ao treino. Monitorar tempo sem corte arbitrário e
abortar com recibo preservado se limites/completude falharem. Registrar
commit limpo, hashes, versões, hardware, seed e argumentos resolvidos.

Saída esperada: três runs completas conferidas, detecções v3 por vídeo e
custos, candidatas de treino e validação posterior. Maior F1 não libera
automaticamente a pipeline: tracking ainda exige contrato HOTA/identidade e
a predição em trajetórias estimadas deve medir ADE/FDE junto com cobertura.
