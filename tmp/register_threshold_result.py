import copy
import hashlib
import json
from pathlib import Path
import yaml

root = Path.cwd()
search = Path('data/tests/detection/threshold/threshold_search_v3_20260908_batch__cfgcdee80e5/search')
run = search / '20260908T141429306548Z__3f73a52__cfg2906caf3f234__srceae1c32fd9__s42'
bench = Path('data/tests/detection/threshold/threshold_search_v3_20260908_batch__cfg1eb41e0e/benchmark')
new_bench = bench / '20260908T141314464252Z__3f73a52__cfgcbefe6ab9f8a__srceae1c32fd9__s42/manifest.json'
figure = Path('data/derived/detection/search_reports/threshold_search_v3_20260908/triagem_threshold_treino.png')
top = json.loads((run / 'shortlist.json').read_text())
qa = json.loads((search / 'verification_20260908.json').read_text())
assert qa['status'] == 'passed'
plan = yaml.safe_load(Path('configs/detection/threshold/search_v3.yaml').read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def text(path): return Path(path).read_text(encoding='utf-8')
def put(path, value): Path(path).write_text(value, encoding='utf-8')
def fmt(value, n=4): return f'{value:.{n}f}'.replace('.', ',')

# Instantiate only the already registered refinement rule; do not execute it.
candidates = {}
for parent in top:
    params = json.loads(Path(parent['manifest_path']).read_text())['config']['params']
    for offset in plan['refinement_plan']['threshold_offsets']:
        resolved = copy.deepcopy(params)
        resolved['threshold_value'] = max(0, min(255, params['threshold_value'] + offset))
        identity = json.dumps(resolved, sort_keys=True, separators=(',', ':'))
        if identity not in candidates:
            t, o, c = (resolved[k] for k in ('threshold_value', 'morph_iterations', 'close_iterations'))
            candidates[identity] = {'configuration_id': f't{t:03d}_o{o}_c{c}', 'method': 'threshold', 'params': resolved, 'parents': []}
        candidates[identity]['parents'].append(parent['configuration_id'])
derived = sorted(candidates.values(), key=lambda row: row['configuration_id'])
assert len(derived) == 117 and len(derived) <= plan['refinement_plan']['maximum_candidates']
refinement = {'status': 'planned_not_executed', 'kind': 'deterministic_instantiation_of_registered_refinement',
              'coarse_manifest': str((root / run / 'manifest.json').resolve()),
              'coarse_manifest_sha256': sha(run / 'manifest.json'),
              'verification_sha256': sha(search / 'verification_20260908.json'),
              'plan_hash': qa['plan_hash'], 'sample_hash': qa['sample_hash'],
              'rule': plan['refinement_plan'], 'candidate_count': len(derived),
              'frames_per_video': 48, 'videos': plan['protocol']['train_ids'],
              'frame_evaluations': len(derived)*576, 'candidates': derived}
with (search / 'refinement_plan_20260908.json').open('x', encoding='utf-8') as f:
    json.dump(refinement, f, ensure_ascii=False, indent=2)

table = '| Ordem | Configuração | F1 macro | Recall macro | MAE de contagem |\n|---:|---|---:|---:|---:|\n'
for row in top:
    table += f"| {row['rank']} | {row['configuration_id']} | {fmt(row['macro_video_f1'])} | {fmt(row['macro_video_recall'])} | {fmt(row['macro_video_count_mae'])} |\n"
result = f'''
### Busca grossa concluída e conferida — 08/09/2026

A otimização foi registrada em `3f73a52`, após **442 testes aprovados**.
O segundo benchmark manteve plano e amostra: laço de 40,8452 s e projeção de
986,31 s, dentro do limite original. A comparação entre as duas execuções
confirmou os 171 arquivos de detecções/GT idênticos byte a byte e todas as
métricas por quadro iguais, exceto o tempo de detecção. A redução observada
de tempo é operacional, não uma estimativa estatística de aceleração.

A busca completa avaliou **171 configurações × 144 quadros = 24.624 casos**.
As 144 imagens contêm 2.961 anotações individuais e 44 agrupamentos, estes em
33 quadros. Cada vídeo contribuiu com 12 quadros. A run terminou em 291,32 s
(laço de 289,06 s), com pico amostrado de RSS de 94,594 MiB e 128.422.020 bytes
nos artefatos dos candidatos. Commit `3f73a52`, Git limpo e proveniência
reverificada antes da classificação. Validação e teste não foram processados.

{table}

Os valores são médias entre os 12 vídeos de treino, calculadas após agregar
os quadros dentro de cada vídeo. A precisão média do primeiro colocado é
0,7374; seu F1 a 15/20 px é 0,7823/0,7836. Houve 15 previsões ignoradas a
10 px. No mesmo candidato, o F1 por vídeo variou de 0,6166 a 0,8982 nesta
amostra, mostrando que a média não descreve igualmente todos os vídeos.
T200/o1/c2 foi reavaliado na v3 e ficou em quarto; o registro congelado
histórico a 15 px permanece intacto. Nenhum desses resultados confirma
generalização, ótimo global, significância estatística ou promoção do método.

A conferência independente aprovou 1.205 arquivos, 1.631.066 comparações
numéricas e 72 verificações de associação com SciPy em casos predeterminados.
Reconstruiu agregações e a ordem dos 171 candidatos; não reutilizou o código
de avaliação ou classificação do projeto. Isso certifica a consistência dos
artefatos verificados, sem certificar completude do gabarito nem desempenho
em quadros não amostrados.

| Artefato local | Abrir |
|---|---|
| Busca completa | [Manifesto](../../{run.as_posix()}/manifest.json) |
| Classificação completa | [ranking.csv](../../{run.as_posix()}/ranking.csv) |
| Cinco candidatos | [shortlist.json](../../{run.as_posix()}/shortlist.json) |
| Conferência independente | [verification_20260908.json](../../{search.as_posix()}/verification_20260908.json) |
| Equivalência dos benchmarks | [benchmark_parity_20260908.json](../../{bench.as_posix()}/benchmark_parity_20260908.json) |
| Figura: curvas e resultados por vídeo | [PNG](../../{figure.as_posix()}) · [SVG](../../{figure.with_suffix('.svg').as_posix()}) |
| Próximo refinamento, ainda não executado | [117 candidatos derivados](../../{search.as_posix()}/refinement_plan_20260908.json) |

O próximo marco implementará e medirá o custo do refinamento previamente
definido. Deduplicar as faixas dos cinco pais produz **117 configurações**,
com 67.392 avaliações nos 576 quadros já preparados: T193–239 com abertura 0
e fechamento 2; T209–239 com abertura 0 e fechamento 1; T185–223 com abertura 1
e fechamento 2. Essa redução de 155 para 117 elimina apenas parâmetros
idênticos, conforme o plano. Área, kernel, polaridade e métrica permanecem
iguais; nenhum desses 117 candidatos foi executado no refinamento ainda.
'''
put('docs/metodologia/BUSCA_THRESHOLD_V3.md', text('docs/metodologia/BUSCA_THRESHOLD_V3.md') + result)
entry = '''## 2026-09-08 — busca grossa v3 concluída; cinco candidatos para refinamento

- Plano anterior à execução: `9940337`; otimização operacional: `3f73a52`,
  com 442 testes aprovados. Os dois benchmarks estão preservados e a comparação
  confirmou CSVs de detecções/GT idênticos nos 171 candidatos.
- A nova projeção (986,31 s) permitiu executar a busca dentro do orçamento
  original. Bateria completa: 171 × 144 = 24.624 avaliações, 291,32 s totais,
  RSS amostrado de 94,594 MiB; Git limpo e conferência final de proveniência.
- Seleção de treino: T224/o0/c2, T208/o0/c2, T224/o0/c1, T200/o1/c2 e
  T208/o1/c2. Primeiro colocado: F1 macro de 0,7753 a 10 px. Nenhuma promoção,
  nova validação ou abertura do teste. Resultado não estima generalização.
- Conferência independente: 1.205 arquivos, 1.631.066 comparações numéricas
  e 72 verificações de associação SciPy aprovadas; ranking reconstruído.
- Próximo marco: implementar e medir o refinamento registrado, com 117
  configurações distintas × 576 quadros = 67.392 avaliações. A lista foi
  derivada dos cinco pais, mas ainda não foi executada.
- Atualizados ficha, matriz, mapa didático, guia de retomada e método LaTeX.
  O PDF continua sem recompilação; arquivos locais seguem fora dos commits.
  [Resultados, figuras e manifestos](../metodologia/BUSCA_THRESHOLD_V3.md#busca-grossa-concluída-e-conferida--08092026).

'''
p='docs/projeto/DIARIO.md';s=text(p);at=s.index('## 2026-09-08');put(p,s[:at]+entry+s[at:])
p='docs/projeto/MATRIZ_EXPERIMENTOS.md';s=text(p)
s=s.replace('| Busca, seleção ou promoção de threshold na v3 | Não executadas |','| Busca grossa e seleção de treino na v3 | Concluídas: 171 × 144 avaliações; cinco candidatos para refinamento; nenhuma promoção |')
s=s.replace('| Plano prospectivo de busca — 08/09 | Registrado: 171 candidatos, 12 quadros por vídeo de treino; benchmark e busca aguardam execução |','| Plano prospectivo de busca — 08/09 | Registrado antes da execução em 9940337; otimização 3f73a52; 442 testes aprovados e conferência independente da busca |\n| Próximo marco | Refinamento de 117 candidatos distintos em 576 quadros, ainda não executado; nova projeção de custo necessária |')
s=s.replace('A auditoria encontrou 5.413', 'A [busca grossa v3](../metodologia/BUSCA_THRESHOLD_V3.md) selecionou para refinamento\nT224/o0/c2, T208/o0/c2, T224/o0/c1, T200/o1/c2 e T208/o1/c2.\nO primeiro atingiu F1 macro de treino de 0,7753 a 10 px, após agregação por\nvídeo. São resultados de seleção em 12 quadros por vídeo, sem promoção.\n\nA auditoria encontrou 5.413',1)
put(p,s)
p='docs/algoritmos/deteccao/threshold_fixo.md';s=text(p)
s=s.replace('finalistas ou vencedoras do contrato v3; a nova busca ainda não foi executada.', 'finalistas ou vencedoras automáticas do contrato v3. A busca prospectiva de\n08/09 reavaliou esses parâmetros sob a nova regra, como descrito abaixo.')
s=s.replace('orçamento prévio, benchmark obrigatório e refinamento desenhado. O plano\nantecede a execução real e não modifica os resultados históricos abaixo.', 'orçamento prévio, benchmark obrigatório e refinamento desenhado. A busca\ngrossa terminou todas as 24.624 avaliações: T224/o0/c2 liderou a amostra de\ntreino com F1 macro de 0,7753; T208/o0/c2, T224/o0/c1, T200/o1/c2 e T208/o1/c2\ncompletam os cinco candidatos. O refinamento ainda não ocorreu. Os 442 testes\nde código e a conferência independente dos resultados passaram. A seleção\nno treino não promove o detector nem altera os resultados históricos.\n\n### Histórico do contrato e do smoke de engenharia')
s=s.replace('geral do threshold e não orienta seleção de parâmetros. Não há busca,\nvalidação científica ou promoção do método na v3.', 'geral do threshold e não orienta seleção de parâmetros. Naquele marco ainda\nnão havia busca na v3. A busca de treino posterior está registrada acima;\na validação e a promoção do método na v3 continuam pendentes.')
put(p,s)
