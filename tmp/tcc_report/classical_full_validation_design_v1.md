# Projeto da validação completa dos detectores clássicos — nota preparatória

Data: 11/09/2026. Documento local ignorado pelo Git. Revisão de código e de
metadados históricos; nenhum pixel foi lido, nenhum detector foi executado e
nenhum resultado novo foi avaliado para produzir esta nota. O refinamento
clássico ainda depende de execução e QA reais; seus dez IDs finalistas e seus
hashes não devem ser preenchidos por suposição. Esta nota não libera validação.

## Decisão proposta

Após refinamento completo e QA independente aprovado, registrar um contrato
novo para dez finalistas, duas de cada família: Otsu, adaptativo, híbrido,
Blob e Watershed. Avaliar cada configuração nos quatro vídeos completos de
validação, exclusivamente `14/19/36/52`: respectivamente 1.470/1.470/1.470/1.440
quadros, total 5.850 por candidata. São 40 runs novas e 58.500 avaliações.

T218 permanece referência histórica autenticada, com quatro runs já existentes:
não constitui uma 11ª candidata executada, não gera quatro runs novas e não
eleva o total novo para 64.350 avaliações. Relatar separadamente: dez candidatas
novas, uma referência histórica, 40 runs novas e quatro referências existentes.

A saída deve selecionar uma configuração por família para desenvolvimento e
apresentar o ranking descritivo entre as dez candidatas sob regras fixas. A
comparação de qualidade com T218 fica em uma tabela identificada como histórica.
Ainda não declarar o detector final de toda a pipeline: falta incorporar YOLO
e os métodos temporais, além de verificar efeito em HOTA/ADE/FDE. Esta validação
é seleção com dados já usados no desenvolvimento do projeto, não teste cego.

## APIs que podem ser reutilizadas

| API / arquivo existente | Uso concreto | Cuidado |
|---|---|---|
| `src/detection/strict_inputs.py:prepare_full_video_input(...)` | Preparar fonte canônica, inventário e hashes de MP4/GT; dimensão, número de quadros e nomes FTID; leitura de metadados sem decodificar frames | Fornecer explicitamente 1.440 para vídeo52; verificar os quatro IDs antes de preparar qualquer entrada |
| `FullVideoInput.gt_frame(frame)` | GT fresco, isolado das estruturas internas, somente para o avaliador | Exigir anotação em todos os índices desta validação; ausência não vira negativo |
| `FullVideoInput.verify_current()` | Revalidar hashes MP4/labels/inventário depois de cada run e ao fechar a bateria | Guarda de metadados não substitui completude da decodificação |
| `src/detection/runner.py:run_on_video(...)` com `full_video_input=prepared` | Detector reiniciado, leitura sequencial, dimensão/tipo, EOF prematuro, leitura adicional para detectar frames extras, export de detecções/GT e métricas | `max_frames=None`, `warmup_frames=0`, sem vídeo anotado; o modo estrito já recusa cortes e aquecimento |
| `script/detection/test/threshold/validate.py:certify_frame_export(...)` | Certificar índices exatos0..N−1, anotação completa, protocolo e agregações do CSV exportado | A função não fixa threshold; pode ser importada sem chamar a CLI histórica |
| `src/experiments/detection_validation.py:summarize_validation_candidate(...)` | Agregar quadros por vídeo e dar peso igual aos quatro vídeos | Exige splitval, quatro vídeos completos e certificado; adicionar family/method fora da função, sem mudar a aritmética |
| `src/experiments/runs.py:RunSnapshot/RunContext` | Commit limpo, hash de fontes, configuração completa, manifestos exclusivos, verificação final | Algoritmo da run deve ser a família real; método threshold para Otsu/adaptativo continua nome da implementação |
| `src/experiments/protocol.py:assert_protocol_access(...)` + `assert_video_ids_in_split(...)` | Guarda semântica e pertencimento aos splits | A guarda geral sozinha não impõe os quatro IDs exatos: o loader novo deve fechar universo e paths |

Não reutilizar o orquestrador `run_validation` inteiro, `load_validation_plan`,
`rank_validation_candidates` ou `_Budget` históricos por alteração temporária
de constantes: estão fixados em threshold, T219/T218, duas candidatas, oito
runs, orçamento1.800s e teto2.000 previsões. A nova bateria precisa de loader,
ranking e orçamento próprios; os módulos/YAMLs/runs históricos ficam intactos.
O ranking novo pode preservar a lógica aritmética do verificador de validação,
mas deve exigir exatamente dez candidatas e não importar o ranker de treino
que exige doze vídeos. Proibir monkeypatch de constantes para executar dados.

## Contrato e parâmetros que devem ficar fechados

1. YAML novo, por exemplo `configs/detection/comparison/classical_validation_v1.yaml`,
   com seu `kind`, `plan_id`, hash canônico, todos os parâmetros resolvidos dos
   dez pais e referências pinadas a refinamento, QA e `family_finalists.json`.
2. Identidades herdadas sem nova grade, reordenação por resultado de validação,
   arredondamento de parâmetros ou overrides de CLI. Verificar método, família,
   chave por chave, tipos JSON/YAML, kernels ímpares e conjunto exato de argumentos
   aceitos pelo construtor. `None` deve continuar `null`, não zero.
3. Split fixo `val`; estágio `validation`; seed42; OpenCV1thread; sem corte de
   quadros, sem resize, sem máscaras GT para o detector; excluir temporal/aprendido
   deste contrato. Ordem de quarenta pares candidata–vídeo embaralhada com seed42.
4. Fonte raiz canônica `data/sources/visem_tracking/dataset/Train`, quatro vídeos
   explicitamente permitidos. O nome externo `Train` da distribuição não redefine
   o split interno `val`. Pin de `configs/protocol/splits.yaml` e inventário
   `data/manifests/visem_tracking.csv`; teste24/38/47/54 continua bloqueado.
5. Avaliador v3 `center_distance_v3_individuals_ignore_clusters_10px`, sensibilidades
   15/20px, indivíduos0/2 e clusters1 segundo a regra existente. Não trocar métricas
   ou usar sensibilidades para escolher depois de observar resultados.
6. Ranking F1 macro por vídeo desc, recall macro desc, MAE de contagem macro asc,
   ID de configuração asc. Tempo não desempata qualidade. Exigir toda a bateria
   para qualquer seleção; depois exigir QA para usar/publicar essa seleção.
7. Sem limite de tempo. Proposta operacional inicial: RSS amostrado2.048MiB,
   artefatos2.048MiB, teto307.200 previsões por quadro, sem truncar. Registrar
   teto como guarda operacional, não prova de limite geométrico dos detectores.
   Se não couber, parar e preservar; um plano operacional novo deve preceder
   nova execução. Não eliminar candidatas que excedam recursos para escolher
   somente entre as que terminaram.

## Autenticação e completude

- Consumir somente refinamento completo, commit limpo, fontes certificadas,
  `parent_parity.json` dos dez pais aprovado, QA independente pinado e dez
  finalistas reconstruídas a partir do ranking completo. Verificar os45
  manifestos e artefatos por hash; confiar no QA numérico anterior identificado,
  sem repetir toda a bateria ou o matching histórico de treino.
- Para preservar o código que gerou o refinamento, reconstruir o inventário
  de fontes de seu commit Git e o hash agregado sobre os mesmos caminhos atuais.
  Arquivos novos são permitidos; mudar bytes de arquivos antigos exige nova
  proveniência e análise de compatibilidade. Essa estratégia já foi testada
  para a passagem busca→refinamento.
- Criar uma entrada `FullVideoInput` por vídeo e compartilhar seu contrato
  imutável entre dez candidatas. Comparar também com o inventário registrado,
  não apenas confiar nos valores retornados por OpenCV.
- Reiniciar/construir detector por candidata–vídeo. Processar inclusive frames
  anotados vazios. Cada criança terá N linhas de métricas, sem duplicação,
  e todas as detecções e GT brutos, inclusive ignorados pelo protocolo.
- Revalidar fontes e pais antes de classificar. Revalidar hashes das40
  crianças e dos artefatos do agregador, além de `RunSnapshot.verify_current()`.
  Uma criança completa isolada não certifica a bateria.
- O loader novo deve rejeitar JSON com chaves duplicadas, NaN, infinito inclusive
  overflow numérico, contagens booleanas/float, paths escapando da raiz/run,
  CSVs com colunas duplicadas, fontes sem hashes e parâmetros extras.

## Riscos operacionais concretos

`run_on_video` mantém todos os rawrows do vídeo e as métricas em listas até
exportar. O quadro BGR isolado usa0,879MiB; 1.470 quadros em cache integral
consumiriam1.292MiB sem overhead, e os quatro vídeos exigiriam5,02GiB só em
pixels. Portanto a versão mínima deve ler sequencialmente um frame por vez,
sem criar cache integral de validação. Quarenta runs sequenciais decodificam
cada vídeo dez vezes; isso é simples e auditável, mas custa mais I/O do que
uma futura bateria simultânea e não deve ser escondido nos tempos.

A lista de detecções/GT pode ser maior que o custo dos pixels, especialmente
para adaptativo/híbrido. O callback ocorre após detecção, antes de matching;
o orçamento deve amostrar RSS em todo frame e antes/depois do export e QA
local. O export faz cópias/materialização em `write_csv_exclusive`; medir
depois do export pode perder um pico instantâneo transitório. Manter a
limitação de RSS amostrado explícita. Evitar paralelizar40runs ou manter10
detectores com40listas simultaneamente sob o teto2GiB.

Se o runner atual não comportar uma candidata completa, o caminho correto
é um kernel novo com export streaming e acumuladores compatíveis, com testes
de paridade antes dos dados. Não cortar frames, suprimir FP ou aumentar o
orçamento dentro da run. Isso pode ser uma revisão operacional prospectiva.

O modo estrito preserva CSVs parciais quando uma falha ocorre dentro do laço,
mas `write_outputs()` após o `try/finally` pode falhar durante exportação;
o wrapper deve sempre gravar manifesto de falha e registrar quais arquivos
existem/hash/bytes sem tentar sobrescrevê-los. `selection.json` eventualmente
escrito antes de uma falha no fechamento jamais será válido sem manifesto
completo e QA aprovado. Preferir escrever seleção por último após as guardas.

O custo futuro não está certificado. Como escala aritmética grosseira,
aplicar a média da busca já conferida43×576 aos58.500 casos daria cerca de
1.776,5s de execução e1.178,9MiB de artefatos. Esses números misturam famílias
e densidades diferentes, vêm de cache de treino e não incluem o custo da nova
decodificação, da preparação, nem do QA. Não são previsão validada, teto de
tempo ou garantia de caber em memória/disco. Após QA do refinamento, estimar
por candidata com seus bytes por frame e pior densidade observada no treino,
registrando fator conservador e separando custo do verificador. Essa conta
nunca altera seleção de candidatas.

## QA independente mínimo

Reutilizar os núcleos puros do QA clássico para CSV, distância, matching SciPy,
regra de clusters e agregação; não importar detector, produtor ou avaliador
para recomputar métricas. Adaptar o universo para4vídeoscompletos×10candidatas.
Evitar matriz quadrada sobre todos os FP: trabalhar no matching retangular
GT-indivíduos×previsões e registrar cardinalidade ótima primeiro, distância
depois. Densidade ruim pode elevar RAM/custo do QA; ele também deve preservar
recibo de falha sem tornar a bateria científica inválida por silêncio.

O QA novo deve conferir40manifestos, hashes de raw/quadros/resumos, parâmetros
dos dez pais, GT exportado contra contratos de entrada e as5.850identidades
físicas repetidas por candidata. Recomputar matching a10/15/20px e avaliação
secundária, ignorados, totais por vídeo, F1macro, ranking e escolha por família.
Não chamar58.500casos de amostras independentes: são quatro vídeos e parâmetros
testados nos mesmos quadros. Conferência de derivados não prova novamente a
decodificação de vídeo; a evidência de EOF/dimensão/hash pertence ao produtor.

Uma adaptação sintética do runner estrito com os dez conjuntos de parâmetros
deve cobrir: EOF curto/extra, mudança de resolução, GT ausente/malformado,
frame vazio, clusters/indivíduos sobrepostos, fonte modificada, CSV parcial,
falha de recursos, parâmetros externos e candidatura incompleta. Não repetir
o smoke/busca/refinamento já encerrados como teste da nova orquestração.

## Reuso autenticado do T218 histórico

Agregador histórico:
`data/tests/detection/threshold/threshold_validation_v3_20260908_batch__cfg56af058b/validation/20260908T175445014964Z__7f47afb__cfg72861b847a20__src71c12fae0d__s42/manifest.json`.

SHA256 `ce0a391b792b8a8081f1ea41aaa7678fcae4973c48cc6a5ce159a27147b3cd55`.
QA aprovado no diretório `validation/verification_20260908_retry2.json`,
SHA256 `9f6b79f5d68b5db59cda035d93036752801b77568d2a24fff8c265865037ffd7`.
Commit original `7f47afb`; fontes originais
`71c12fae0df479e729b534d9b042e7617299c0ea9ecb5c0fea7efdf87ed3085d`.
Esses hashes foram conferidos nesta revisão por leitura de metadados.

Os quatro manifestos T218 devem ser encontrados pelo `configuration_id`
e `config.input.video_id` do agregador autenticado, sem confiar em glob de
nome/pasta. Seus hashes e `input_hash` registrados são:

| Vídeo | SHA256 manifesto filho | input_hash histórico |
|---|---|---|
|14|b104a153bb9b87f870c6729151dfd2b231e061a827358b52685368f1aaa8be63|e5bd90f70ecca7f7ae6b0c06a85c8ad8be1291845e628f5b89c234a54dc45cfd|
|19|cb32d195910c2017e4e68cd922bf1cb7ee309489aea0701dbb863fe00633dab2|1cc679ec1ed425c6d663491cbabe63565fdd7f42e471eccafbef3c657814d6fc|
|36|fd8826b4cfb97ac79dcc95e9e72ec45e67703b8dcf7891d0ec214f96bf4b01be|7e48b644e714eb28fb21c8cb9153bbb15eae4617a46d6855456d0d448edc1701|
|52|bdf9fd02f5739794b6b0f557d70cb0c2c4cf537869d4422d101535113ba76042|5b1f9c779f2e6e9865862c3968a091f65949d9fe92af3c49564f3bdd4143966f|

Conferir todos os artefatos desses filhos, os quatro contratos completos de
entrada e o QA pinado. Recompor a agregação macro do T218 usando os resumos
históricos autenticados. Não misturar as crianças T219, que também estão no
agregador. Confirmar T218/o0/c2,área3..300,kernel3,inversãofalse,blur1,regra v3.
Parâmetros omitidos por YAML antigo devem ser resolvidos pela implementação
daquele commit, com evidência dos defaults; não completar por defaults atuais
sem conferência. A paridade já aprovada do T218 no treino constitui evidência
complementar, não uma nova medição nos vídeos de validação.

Comparar os contratos novos com os `input_hash` acima e com hashes MP4/GT,
dimensões, cobertura e inventário. Se só metadados de ambiente/backend/path
mudarem, preservar ambos os hashes e exigir regra explícita de compatibilidade
antes de afirmar entradas equivalentes; não apagar diferenças silenciosamente.
Não exigir que o hash de todo o repositório atual seja igual ao de7f47afb:
há outros módulos adicionados/modificados desde então. O histórico conserva
seus hashes; verificar as implementações relevantes ou sua cadeia de paridade.

Exportar `historical_t218_reference.json` com hashes originais, quatro filhos,
compatibilidade de entradas, escopo development_only e `reexecuted=false`.
Tempo, RAM, hardware e versão OpenCV históricos mantêm os valores/datas antigos;
não entram numa comparação contemporânea de custo nem são atribuídos ao novo
commit. T218 é referência previamente ajustada, com esforço diferente das novas
famílias. Reusar seus números não produz independência estatística.

## Interface futura sugerida — ainda inexistente

```
python -m script.detection.test.validate_classical --plan configs/detection/comparison/classical_validation_v1.yaml --dry-run
python -m script.detection.test.validate_classical --plan configs/detection/comparison/classical_validation_v1.yaml
python -m script.detection.test.verify_classical_validation --manifest <novo_manifesto> --plan configs/detection/comparison/classical_validation_v1.yaml --output <qa_exclusivo.json>
```

Dry-run deve autenticar pais/recibos e plano sem preparar vídeos de validação.
Execução não aceita override científico, outros IDs, `all`, teste/folds ou
`max_frames`. Um `--output-root` facultativo pode existir apenas para testes
sintéticos; a CLI científica deve usar diretório de runs exclusivo padrão.

Artefatos mínimos do agregador: `planned_candidates.json`, `planned_pairs.json`,
`planned_frames.json`, `input_contracts.json`, `parent_authentication.json`,
`historical_t218_reference.json`, `video_metrics.csv`, `candidate_metrics.csv`,
`ranking.csv`, `family_selection.json`, manifesto com40filhos e hashes. Cada
criança exporta `detections.csv`, `frame_metrics.csv`, `summary.json`, certificados
de cobertura e de entrada. A publicação espera QA completo; falha preserva
todas as evidências e mantém seleção inválida.

Depois dessa validação, registrar uma decisão de desenvolvimento por família
e sua relação com T218. Treinamento/validação YOLO, temporais com aquecimento,
comparação dos rastreadores e predição causal continuam etapas próprias.
Maior F1 de detecção não garante melhor rastreamento ou menor erro futuro.
