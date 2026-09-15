"""Record completed, independently verified training comparison in project docs."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
summary_path = ROOT / 'data/derived/detection/comparison_reports/classical_v1_20260911/summary.json'
summary = json.loads(summary_path.read_text(encoding='utf-8'))
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return (ROOT / path).read_text(encoding='utf-8')
def write(path, text): (ROOT / path).write_text(text, encoding='utf-8', newline='\n')
def fmt(value, digits=6): return f'{value:.{digits}f}'.replace('.', ',')
def count(value): return f'{value:,}'.replace(',', '.')

assert digest(ROOT / summary['source_manifest']) == summary['source_manifest_sha256']
assert digest(ROOT / summary['verification']) == summary['verification_sha256']
run = json.loads(read(summary['source_manifest']))
qa = json.loads(read(summary['verification']))
assert run['status'] == 'complete' and run['git_dirty'] is False
assert qa['status'] == 'passed' and qa['historical_t218_parity']['frames_compared'] == 576
smoke_path = ROOT / run['config']['provenance']['smoke']['path']
smoke = json.loads(smoke_path.read_text(encoding='utf-8'))
smoke_qa_path = smoke_path.parent.parent / 'verification_20260911.json'
smoke_qa = json.loads(smoke_qa_path.read_text(encoding='utf-8'))
assert smoke['status'] == 'complete' and smoke_qa['status'] == 'passed'
assert smoke_qa['manifest_sha256'] == digest(smoke_path)

table = '| Família | Configuração da grade | F1 macro a 10 px | Precisão macro | Recall macro | ms/quadro |\n|---|---|---:|---:|---:|---:|\n'
for row in summary['best_per_family']:
    table += '| '+row['label']+' | `'+row['configuration_id']+'` | '+' | '.join(fmt(row[k], 6 if k != 'detection_ms' else 3) for k in ('f1','precision','recall','detection_ms'))+' |\n'

evidence = f'''Busca: `{summary['source_manifest']}`.
SHA256 do manifesto: `{summary['source_manifest_sha256']}`.
QA: `{summary['verification']}`.
SHA256 do QA: `{summary['verification_sha256']}`.
Fontes da execução: `{run['source_hash']}`.

Smoke v2: `{smoke_path.relative_to(ROOT).as_posix()}`.
Manifesto SHA256 `{digest(smoke_path)}`.
QA: `{smoke_qa_path.relative_to(ROOT).as_posix()}`.
QA SHA256 `{digest(smoke_qa_path)}`.
'''

results = f'''## Resultados da busca e conferência — 11/09/2026

A revisão operacional v2 concluiu o smoke e a busca com Git limpo em
`{run['git_sha']}`. O smoke cobriu 43 configurações × 12 quadros = 516
avaliações; não selecionou candidatas. A busca cobriu as mesmas 43
configurações × 576 quadros = **24.768 avaliações**, nos 12 vídeos de treino.
Foram mantidos todos os candidatos e todas as previsões, inclusive
superdetecções. A falha operacional v1 permanece preservada acima.

{table}
Cada linha mostra a melhor configuração **desta grade** dentro da família.
A métrica agrega TP/FP/FN dentro do vídeo e depois dá peso igual aos 12
vídeos. Não é uma média de F1 por quadro. A grade tem esforço desigual entre
famílias e T218 foi ajustado anteriormente; não descreve os máximos possíveis
de cada algoritmo. Precisão e recall também são médias por vídeo: seu F1
harmônico não precisa coincidir com o F1 macro da tabela.

As 11 candidatas registradas em `family_finalists.json` são as duas primeiras
de cada uma das cinco famílias pesquisadas e a referência T218. São pais
para a próxima etapa, não configurações promovidas. Ainda não houve
refinamento dessas novas famílias, validação comparativa completa, teste,
confirmação por folds ou escolha da pipeline. MOG2/KNN e YOLO não participaram
desta bateria; necessitam protocolo temporal e treinamento próprios.

A busca durou {fmt(run['elapsed_seconds'])} s após a autenticação inicial do
cache ({fmt(run['summary']['cache_validation_seconds'])} s). O laço de
candidatas durou {fmt(run['summary']['candidate_loop_seconds'])} s. RSS máximo
amostrado {fmt(run['summary']['ram_rss_peak_mb'], 3)} MiB, em
{count(run['summary']['resource_samples'])} medições;
{count(run['summary']['candidate_artifact_bytes'])} bytes de artefatos das
candidatas. Esse número não inclui os arquivos do agregador. Os limites de
2.048 MiB de RSS e artefatos foram respeitados. O custo por quadro da tabela
mede o detector sobre imagem em cache; não é FPS da pipeline completa.

A conferência independente da busca passou na primeira tentativa:
{count(qa['files_checked'])} arquivos, {count(qa['comparisons'])} comparações,
{count(qa['numeric_comparisons'])} numéricas e
{count(qa['scipy_matchings'])} matchings SciPy, em {fmt(qa['elapsed_seconds'])} s.
Maior diferença numérica: {qa['maximum_numeric_difference']!r}.
T218 reproduziu os centros/GT e métricas dos mesmos 576 quadros da run de
refinamento anterior, exceto tempo e identificação da nova execução.
O QA não refaz inferência ou decodificação; verifica os derivados autenticados
e reconstrói as associações, agregações, ranking e candidatas seguintes.
As limitações e eventuais empates ótimos estão descritos no recibo completo.

O QA do smoke também passou: {count(smoke_qa['files_checked'])} arquivos,
{count(smoke_qa['comparisons'])} comparações,
{count(smoke_qa['scipy_matchings'])} matchings, paridade T218 nos 12 quadros.
O smoke e a busca são execuções diferentes e conservam seus próprios recibos.

{evidence}
A tabela e a figura descritiva derivada estão em
`data/derived/detection/comparison_reports/classical_v1_20260911/`, com
manifesto de origem, QA e hashes em `summary.json`. Os CSVs completos e as
sensibilidades de 15/20 px permanecem nas runs.

Próximo marco: resolver as vizinhanças prospectivas desta seção anterior em
novo YAML e executor de refinamento, incluindo pais/deduplicação, e conferir
os resultados. Depois, validar as finalistas nos quatro vídeos completos.
YOLO deve completar a comparação antes da escolha do detector da cadeia.
Tracking terá comparação própria: F1 de detecção não substitui HOTA,
identidade ou cobertura; predição deve medir ADE/FDE sobre trajetórias
estimadas, além dos controles GT já existentes.
'''
protocol_path = 'docs/metodologia/COMPARACAO_DETECTORES_CLASSICOS_V1.md'
assert '## Resultados da busca e conferência' not in read(protocol_path)
write(protocol_path, read(protocol_path).rstrip()+'\n\n'+results)

diary = f'''## 2026-09-11 — busca comparativa clássica concluída e conferida

Concluídos smoke e busca em `{run['git_sha']}`, com Git limpo e proveniência
revalidada antes da seleção. A busca avaliou 43 configurações de seis
famílias nos mesmos 576 quadros dos 12 treinos: **24.768 avaliações**.
QA independente aprovado na primeira tentativa, incluindo paridade T218 em
576 quadros: {count(qa['files_checked'])} arquivos,
{count(qa['comparisons'])} comparações e {count(qa['scipy_matchings'])} matchings.
Tempo de bateria {fmt(run['elapsed_seconds'])} s; RSS amostrado
{fmt(run['summary']['ram_rss_peak_mb'], 3)} MiB. O QA durou {fmt(qa['elapsed_seconds'])} s.

{table}
São as melhores configurações da grade por família, selecionadas **no treino**.
T218 já foi ajustado antes e o esforço entre famílias é desigual. As 11
candidatas seguintes não são promoção nem escolha final da pipeline. O
próximo passo é refinamento prospectivo e validação; YOLO e MOG2/KNN têm
etapas próprias, seguidas pela comparação de rastreadores e preditores.
Nenhum resultado novo de HOTA, ADE/FDE com fluxo ou treinamento aprendido.

[Protocolo, recursos, caminhos e hashes completos](../metodologia/COMPARACAO_DETECTORES_CLASSICOS_V1.md#resultados-da-busca-e-conferência--11092026).
O smoke v1 interrompido permanece registrado; a revisão v2 apenas ampliou o
teto operacional de previsões, sem truncar ou mudar dados/grade/métricas.
Os commits documentais seguintes não mudam a proveniência das runs.

'''
diary_path = 'docs/projeto/DIARIO.md'
old = read(diary_path)
index = old.index('## 2026-09-11')
write(diary_path, old[:index]+diary+old[index:])

continuity_path = 'docs/metodologia/CONTINUIDADE_EXPERIMENTAL_V1.md'
old = read(continuity_path)
old = old.replace('A primeira\nbateria em implementação está descrita em', 'A primeira\nbateria concluída e conferida está descrita em')
old = old.replace('576 quadros de treino. Ela começa por smoke e busca; refinamento, validação\ne YOLO têm etapas próprias.', '576 quadros de treino, totalizando 24.768 avaliações. Smoke e busca passaram\npela conferência independente; refinamento, validação e YOLO têm etapas próprias.')
old = old.replace('contratos executáveis de cada bateria, não registra resultados novos e não\ndeclara o nível 8 concluído.', 'contratos executáveis de cada bateria. Os resultados da comparação clássica\nestão no protocolo vinculado; a ablação com fluxo ainda não foi executada.')
old = old.replace('O marco científico atual continua sendo o benchmark compacto 8a, conferido\nem 09/09.', 'O marco mais recente de detecção é a busca comparativa de 11/09. Na frente\nde fluxo, permanece o benchmark compacto 8a, conferido em 09/09.')
write(continuity_path, old)

readme = read('README.md')
marker = '## Comece por aqui'
readme = readme.replace(marker, '**Estado em 11/09/2026:** busca comparativa de seis famílias clássicas concluída\ne conferida no treino: 43 configurações, 576 quadros e 24.768 avaliações.\nSeguem refinamento, validação e YOLO antes da escolha do detector;\nrastreamento e predição terão comparações próprias.\n\n'+marker, 1)
readme = readme.replace('Acompanhar a busca atual de threshold no treino', 'Consultar a busca concluída de threshold no treino')
write('README.md', readme)

handoff = f'''## Continuidade vigente — comparação clássica conferida em 11/09/2026

A orientação atual é testar e validar os demais algoritmos antes de escolher
a cadeia de tracking/predição. **Smoke e busca clássica concluídos e
conferidos** em `{run['git_sha']}`, Git limpo: 43 configurações de seis famílias,
576 quadros dos 12 treinos, 24.768 avaliações. Não repetir essas baterias.
Conferência: {count(qa['files_checked'])} arquivos,
{count(qa['comparisons'])} comparações, {count(qa['scipy_matchings'])} matchings
SciPy, paridade T218 nos 576 quadros. Busca {fmt(run['elapsed_seconds'])} s,
RSS amostrado {fmt(run['summary']['ram_rss_peak_mb'], 3)} MiB.

{evidence}
Plano executado: `configs/detection/comparison/classical_v1_operational_v2.yaml`.
O v1 e sua falha por limite de 2.000 previsões permanecem preservados; v2
mudou somente identidade/linhagem e teto operacional para 307.200. Não truncar
previsões nem reinterpretar a falha como comparação concluída. Protocolo e
resultados em `docs/metodologia/COMPARACAO_DETECTORES_CLASSICOS_V1.md`.

Próximo marco: novo YAML/executor de **refinamento** sobre as 11 candidatas
em `family_finalists.json` (T218 fixa; dois pais por família pesquisada).
Resolver a vizinhança um eixo por vez, previamente definida no protocolo,
incluindo pais e deduplicação, até 54 configurações antes de deduplicar.
Depois, nova validação das dez finalistas em quatro vídeos completos;
T218 histórica só entra após autenticação, preservando custo/commit próprios.
Não relaxar a CLI histórica `threshold/validate.py`: criar consumidor novo.
A CLI `compare_classical.py` atual aceita apenas smoke/search; não libera
refinamento, validação, teste ou promoção. A nova QA deverá manter paridade.

Ambiente `.venv-ml` validado sinteticamente na RTX 4070 Ti: torch 2.9.1+cu128,
torchvision 0.24.1+cu128, ultralytics 8.4.147. Recibo
`data/derived/project_audits/learned_environment/20260911_validation_v1.json`;
hash `29414ce0667c40ccd23e317cc86c07b6ed048e2efa249d968fb60c3fa907312b`.
Foi executado em a924fe5 com Git sujo declarado; não reatribuir o código.
YOLO precisa de cópias derivadas autenticadas: a biblioteca escreve caches
mesmo com cache=False e pode reparar JPEG; não apontar às fontes nem usar
hardlinks. Fixar receita/checkpoints por protocolo próprio, pesos/hashes,
classes 0/2 e regra de clusters v3. O smoke não treinou YOLO/RAFT/LSTM.

Contrato de rastreamento em `docs/metodologia/RASTREAMENTO_COMPARACAO_V1.md`
e `configs/tracking/comparison_v1.yaml`: rascunho não executável, com cinco
métodos. HOTA oficial, política de clusters/lacunas, adaptador sem IDs GT e
cache de detecções comum ainda devem ser implementados/conferidos.
MOG2/KNN precisam de clipes cronológicos e aquecimento; não usar os quadros
espaçados desta busca como se fossem sequências consecutivas.

A primeira ablação causal nas 10.848 janelas disponíveis continua prevista.
O histórico do 8a abaixo continua válido para fluxo: não existe ADE/FDE real
com fluxo, HOTA real atual ou teste da hipótese. O teto histórico de 120 min
não limita novos planos, conforme autorização de 11/09; preservar YAML/run
anteriores, recursos, causalidade, exclusões e completude. Teste/folds
continuam bloqueados e sua exposição histórica declarada.

O relatório e atlas locais incorporam os resultados de 11/09: 19 capítulos,
seis figuras e quatro laboratórios. Componentes e QA em `tmp/tcc_report/`;
figura/resumo autenticado em
`data/derived/detection/comparison_reports/classical_v1_20260911/`.
Snapshot e registro da edição:
`data/derived/project_audits/general_20260911/classical_comparison_edition/`.
Os HTMLs, este guia, instruções locais e monografia permanecem fora dos commits.

'''
for path in ('AGENTS.md', 'docs/projeto/NAVEGACAO.md'):
    old = read(path)
    start = old.index('## Continuidade vigente')
    # Replace the old top handoff, keeping dated history below it.
    if path == 'AGENTS.md':
        end = old.index('## Navegação e retomada')
    else:
        end = old.index('Atualizado em 2026-09-11.')
    old = old[:start]+handoff+old[end:]
    old = old.replace('Registro atual: **nível 8a concluído e conferido', 'Registro anterior da frente de fluxo: **nível 8a concluído e conferido', 1)
    old = old.replace('com atalho na raiz, 19 capítulos, cinco figuras, quatro laboratórios', 'com atalho na raiz, 19 capítulos, seis figuras, quatro laboratórios', 1)
    old = old.replace('Síntese didática completa ampliada em 10/09/2026', 'Síntese didática completa atualizada em 11/09/2026', 1)
    old = old.replace('O próximo marco é registrar e executar a ablação exploratória nos derivados disponíveis, conforme o plano de 11/09.', 'O próximo marco é refinar e validar os novos detectores, com preparação do YOLO em paralelo.')
    old = old.replace('É atualização documental: o estado científico permanece o marco 8a de 09/09.', 'A edição de 11/09 incorpora a busca comparativa concluída; o fluxo mantém o marco 8a de 09/09.')
    old = old.replace('ampliado em 10/09/2026.', 'atualizado em 11/09/2026.', 1)
    old = old.replace('e a leitura de arquivos reais. Há busca, cinco figuras científicas', 'e a leitura de arquivos reais. Há busca, seis figuras científicas', 1)
    old = old.replace('É uma síntese documental local: não acrescenta experimentos nem muda o marco\ncientífico. O nível 8a está concluído e conferido, mas sua projeção de tempo excedeu o\nlimite. O plano de 11/09 prioriza a primeira ablação nos derivados disponíveis, com\nnovo contrato; a extração completa terá plano próprio.', 'O gerador documental não executa modelos. Esta edição incorpora a busca\ncomparativa real de 11/09, executada e conferida separadamente. O nível 8a\npermanece o último resultado de fluxo; sua projeção excedeu o limite histórico.\nRefinamento/validação dos detectores e YOLO são as próximas etapas; ablação\ne extração ampliada continuam previstas sob contratos próprios.')
    write(path, old)

print(json.dumps({'status':'scientific_docs_and_local_handoff_updated', 'run_commit':run['git_sha'], 'source_manifest_sha256':summary['source_manifest_sha256']}, ensure_ascii=False))
