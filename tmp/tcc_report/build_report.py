"""Build an offline explanatory report from audited project records, no experiments."""
from pathlib import Path
from html import escape
from html.parser import HTMLParser
import base64
import hashlib
import json
import re
import struct
from datetime import datetime, timezone
from report_extensions import artifact_fragments

ROOT = Path(__file__).resolve().parents[2]
PARTS = ROOT / 'tmp/tcc_report'
OUT = ROOT / 'docs/projeto/RELATORIO_COMPLETO_TCC.html'
RUN = ROOT / 'data/tests/prediction/baselines/prediction_baselines_v1__cfgc874ef20/development/20260908T202138821137Z__5289c93__cfg11aeec0be9f3__srcf738122f1f__s42'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(name): return (PARTS / name).read_text(encoding='utf-8')
def fmt2(value): return f'{value:.2f}'.replace('.', ',')
def fmt(value): return f'{value:.6f}'.replace('.', ',')
def count(value): return f'{value:,}'.replace(',', '.')

# Filled only after the new run and its independent audit have completed.
# Missing pins stop generation before replacing the current report.
COMPACT_RUN = 'data/tests/flow/farneback/farneback_compact_benchmark_v1__cfgeae42bba/benchmark/20260910T023738734548Z__6110c44__cfgf794175a7060__srca19f8367f9__s42'
COMPACT_QA = 'data/tests/flow/farneback/farneback_compact_benchmark_v1__cfgeae42bba/benchmark/verification_20260909.json'
COMPACT_MANIFEST_SHA256 = '72c7df2d895d1fa02014dfa1100a1a7defc8351ea19d86392ad09e5473fcd278'
COMPACT_QA_SHA256 = '20af88c5930434685a86330d98692f99d9a429f0e0e61723ae41138e1af1435c'
assert all((COMPACT_RUN, COMPACT_QA, COMPACT_MANIFEST_SHA256, COMPACT_QA_SHA256)), \
    'Await the complete compact benchmark, independent audit and immutable pins before building'
compact_run = ROOT / COMPACT_RUN
compact_qa_path = ROOT / COMPACT_QA
assert sha(compact_run / 'manifest.json') == COMPACT_MANIFEST_SHA256
assert sha(compact_qa_path) == COMPACT_QA_SHA256
compact_manifest = json.loads((compact_run / 'manifest.json').read_text(encoding='utf-8'))
compact_qa = json.loads(compact_qa_path.read_text(encoding='utf-8'))
assert compact_manifest['status'] == 'complete' and compact_manifest['git_dirty'] is False
assert compact_manifest['git_sha'] == '6110c44'
assert compact_qa['status'] == 'passed'
assert compact_qa['run_manifest_sha256'] == COMPACT_MANIFEST_SHA256
compact_summary = compact_manifest['summary']
assert compact_summary['prediction_evaluated'] is False
assert compact_summary['hypothesis_evaluated'] is False
assert compact_summary['full_extraction_released'] is False
assert (compact_summary['frames'], compact_summary['forward_fields'], compact_summary['backward_fields']) == (720, 708, 24)
compact_projection = compact_summary['projection']
assert compact_projection['full_extraction_released'] is False
assert compact_projection['full_rss_certified'] is False
assert (compact_run / 'summary.json').is_file()

compact_links = (
    f'<a href="../../{COMPACT_RUN}/manifest.json">Manifesto do benchmark</a> · '
    f'<a href="../../{COMPACT_RUN}/summary.json">resumo completo</a> · '
    f'<a href="../../{COMPACT_QA}">conferência independente</a>.'
)
compact_table = '<table><thead><tr><th>Treino</th><th>Janelas</th><th>Amostras únicas</th><th>Usos nas histórias</th><th>Janelas com as 5 finais válidas</th></tr></thead><tbody>'
for row in compact_summary['videos']:
    compact_table += '<tr><td>'+escape(row['video_id'])+'</td>'+''.join(
        '<td>'+count(row[key])+'</td>' for key in ('windows', 'unique_samples', 'historical_uses', 'eligible_last5_windows')
    )+'</tr>'
compact_table += '<tr><td><strong>Total</strong></td>'+''.join(
    '<td><strong>'+count(compact_summary[key])+'</strong></td>'
    for key in ('windows', 'unique_samples', 'historical_uses', 'eligible_last5_windows')
)+'</tr></tbody></table>'
compact_resources = compact_manifest['resources']
compact_loop_projection = 2 * sum(row['loop_seconds'] * term['loop_scale']
    for row,term in zip(compact_summary['videos'],compact_projection['terms']))
compact_table_projection = 2 * sum(row['table_seconds'] * term['table_scale']
    for row,term in zip(compact_summary['videos'],compact_projection['terms']))
compact_checkpoint_projection = 2 * sum(row['checkpoint_seconds'] for row in compact_summary['videos'])
compact_fixed_projection = 2 * compact_projection['fixed_seconds']
compact_metrics = (
    f'<p><strong>Resultado observado:</strong> {count(compact_summary["windows"])} janelas, '
    f'{count(compact_summary["unique_samples"])} amostras únicas e {count(compact_summary["historical_uses"])} usos históricos. '
    f'{count(compact_summary["valid_samples"])} amostras foram numericamente válidas; '
    f'{count(compact_summary["unique_samples"]-compact_summary["valid_samples"])} inválidas permaneceram contabilizadas. '
    f'{count(compact_summary["eligible_last5_windows"])} janelas têm as cinco amostras finais válidas. '
    'São contagens dos prefixos, não do treino completo nem de indivíduos independentes.</p>'
    +compact_table+
    f'<p><strong>Custo medido da run:</strong> {fmt(compact_manifest["elapsed_seconds"])} s; '
    f'RSS máximo amostrado {fmt(compact_resources["ram_rss_peak_mb"])} MiB; '
    f'{count(compact_qa["new_run_bytes_including_manifest"])} bytes finais. '
    f'Foram preservados {count(compact_qa["new_artifacts_verified"])} artefatos, além do manifesto. '
    'O tempo inclui as etapas do produtor; a conferência independente tem custo separado.</p>'
    f'<p><strong>Projeção registrada:</strong> {fmt(compact_projection["projected_seconds"])} s e '
    f'{fmt(compact_projection["projected_artifact_bytes"]/1024**2)} MiB de artefatos, já com margem 2× e reserva de metadados. '
    +('O indicador ficou dentro dos dois limites de planejamento. ' if compact_projection['status']=='provisional_within_budget'
      else 'O indicador excedeu ao menos um dos limites de planejamento. ')+
    '<strong>Isso não certifica o custo, a memória ou a cobertura dos vídeos completos.</strong></p>'
    '<div class="callout warning"><strong>A run concluiu; a projeção não liberou a escala.</strong>'
    f'<p>O tempo projetado de {fmt2(compact_projection["projected_seconds"]/60)} minutos excedeu os 120 minutos registrados. '
    'Os artefatos projetados ficaram abaixo de 4.096 MiB, mas os dois limites precisam ser respeitados. '
    'Esse resultado é útil: mostra onde investigar antes de ocupar horas com a extração completa. '
    'O teto não será elevado retroativamente para chamar este indicador de aprovado.</p></div>'
    f'<p>A decomposição da projeção atribui {fmt(compact_loop_projection)} s ao laço '
    f'({fmt2(100*compact_loop_projection/compact_projection["projected_seconds"])}% do total), '
    f'{fmt(compact_table_projection)} s às tabelas, {fmt(compact_checkpoint_projection)} s aos sentinelas '
    f'e {fmt(compact_fixed_projection)} s ao custo fixo; todos já incluem o fator 2×. '
    'O laço reúne decodificação, estimação forward, amostragem e coleta de testemunhos. '
    '<strong>A medição atual não separa essas operações.</strong> O próximo passo é instrumentá-las e registrar '
    'uma avaliação operacional controlada, preservando parâmetros, coorte, orçamentos e artefatos originais. '
    'Só depois será possível fechar o plano de retenção/memória e a extração ampliada.</p>'
)
compact_values = {
    'COMPACT_OVERVIEW': 'O marco 8a concluiu e conferiu o benchmark compacto dos 12 prefixos de treino. Sua projeção excedeu o teto histórico de tempo. A ablação nos derivados permanece prevista; a comparação dos demais detectores avançou em 11/09 e está documentada neste relatório.',
    'COMPACT_PROVENANCE_INTRO': 'O benchmark compacto foi executado em <code>6110c44</code>, após 1.728 testes em 181,93 s e antes de sua conferência independente.',
    'COMPACT_HISTORY_EVIDENCE': '<code>6110c44</code>, 1.728 testes antes dos pixels; 720 quadros, 708 campos forward e 24 backward. Run e conferência completas, sem avaliação de preditor.',
    'COMPACT_RESULT_STATUS': '<strong>Marco 8a concluído e conferido.</strong> Código e protocolo foram registrados em <code>6110c44</code>, antes dos pixels, após 1.728 testes em 181,93 s.',
    'COMPACT_METRICS': compact_metrics,
    'COMPACT_QA': (
        f'<p><strong>Conferência independente aprovada na primeira tentativa:</strong> {count(compact_qa["files_verified"])} arquivos, '
        f'{count(compact_qa["comparisons"])} comparações, das quais {count(compact_qa["numeric_comparisons"])} numéricas, '
        f'em {fmt(compact_qa["elapsed_seconds"])} s. Maior diferença absoluta: '
        f'{compact_qa["max_absolute_difference"]:.6e}, abaixo da tolerância registrada de 10⁻⁹. '
        f'Foram reconstruídas todas as {count(compact_qa["unique_samples_rebuilt"])} interpolações e '
        f'{count(compact_qa["historical_uses_rebuilt"])} ligações históricas, com chaves e coordenadas de origem conferidas. '
        'Contagens, coordenadas e hashes têm regras exatas; a tolerância numérica vale para interpolações e diagnósticos. '
        'Essas comparações verificam a representação e a matemática, não criam novas amostras estatísticas.</p>'
    ),
    'COMPACT_ARTIFACT_LINKS': compact_links,
    'COMPACT_ROADMAP_STATUS': 'O marco 8a acrescentou o benchmark compacto dos 12 prefixos, com run e conferência concluídas.',
    'COMPACT_NAVIGATION_LINKS': compact_links,
}

manifest=json.loads((RUN/'manifest.json').read_text(encoding='utf-8'))
assert manifest['status']=='complete' and manifest['git_sha']=='5289c93' and manifest['git_dirty'] is False
assert sha(RUN/'manifest.json')=='fefb77906d3af9629c22a21b4c989f62d9f295f73f65708894c8672975fe2f2d'
qa=RUN.parent/'verification_20260908.json'
assert json.loads(qa.read_text())['status']=='passed'
assert sha(qa)=='9bc9cd8beee29636470e747851e735ab481f23afcdd4b41ef36c7acf12550b69'
sources=json.loads(read('metrics_sources.json'))
inventory=json.loads(read('folder_inventory.json'))
FLOW_RUN = ROOT / 'data/tests/flow/farneback/farneback_causal_smoke_v1__cfg0609f968/smoke/20260909T203917667291Z__16eecbb__cfgf7e0afa345b3__src3f9307153a__s42/'
FLOW_QA = ROOT / 'data/tests/flow/farneback/farneback_causal_smoke_v1__cfg0609f968/smoke/verification_20260909_retry1.json'
assert sha(FLOW_RUN/'manifest.json') == 'fff845df9b10c743b227e0f459b502218677840d021c6190736041507b7f1d98'
assert sha(FLOW_QA) == 'b44db2e80e727afe067ee5ba6b95b97d7c2a9c32491fec045bf54ec9fa7c6652'
assert json.loads(FLOW_QA.read_text())['status'] == 'passed'
figures=[]

def figure(relative,alt,caption):
    p=ROOT/relative
    raw=p.read_bytes()
    assert raw[:8] == b'\x89PNG\r\n\x1a\n'
    width,height=struct.unpack('>II',raw[16:24])
    data=base64.b64encode(raw).decode()
    figures.append({'path':relative,'sha256':sha(p),'bytes':p.stat().st_size})
    return f'<figure><img src="data:image/png;base64,{data}" alt="{escape(alt,quote=True)}" width="{width}" height="{height}" loading="eager"><figcaption>{escape(caption)} <a href="../../{relative}">Abrir PNG original</a> · <a href="../../{str(Path(relative).with_suffix(".svg")).replace(chr(92),"/")}">SVG original</a></figcaption></figure>'


CLASSICAL_RESULT_PATH = ROOT / 'data/derived/detection/comparison_reports/classical_v1_20260911/summary.json'
assert sha(CLASSICAL_RESULT_PATH) == 'd2f6889e80f971d2684cbf7277208b91fa80301608f15030ee0b4cfcc45ef282'
classical_result = json.loads(CLASSICAL_RESULT_PATH.read_text(encoding="utf-8"))
assert sha(ROOT / classical_result["source_manifest"]) == classical_result["source_manifest_sha256"]
assert sha(ROOT / classical_result["verification"]) == classical_result["verification_sha256"]
for filename, expected_hash in classical_result["figures"].items():
    assert sha(CLASSICAL_RESULT_PATH.parent / filename) == expected_hash

REFINEMENT_RESULT_PATH = ROOT / 'data/derived/detection/comparison_reports/classical_refinement_v1_20260911/revision_02/summary.json'
assert sha(REFINEMENT_RESULT_PATH) == 'a17521606f2522d90689d93e77783990827e7b9ed2a22f95b3cb19260615f940'
refinement_result = json.loads(REFINEMENT_RESULT_PATH.read_text(encoding="utf-8"))
assert sha(ROOT / refinement_result["source_manifest"]) == refinement_result["source_manifest_sha256"]
assert sha(ROOT / refinement_result["verification"]) == refinement_result["verification_sha256"]
for filename, expected_hash in refinement_result["figures"].items():
    assert sha(REFINEMENT_RESULT_PATH.parent / filename) == expected_hash
assert sha(ROOT / 'data/datasets/yolo/materialized/yolo_dataset_v1_20260911__cfgfbd698da/preparation/20260911T161002135908Z__ca68f16__cfgf16cf2018592__srcf2ecb55da1__s42/manifest.json') == 'e13f65035d1ae90dcb2337a8942022d70a45cfbb926a611df21b83add2c8bf42'
assert sha(ROOT / 'data/datasets/yolo/materialized/yolo_dataset_v1_20260911__cfgfbd698da/preparation/verification_20260911.json') == '0ad645d9cd20825984b70d5dab2b6d5dfd1a36970e10bd2a8b0129f81b2490be'

core=read('core.html')
core=core.replace('{{FIG_REFINEMENT}}',figure('data/derived/detection/comparison_reports/classical_refinement_v1_20260911/revision_02/refinamento_classicos_treino.png','F1 por vídeo e média de cada família após refinamento; referência T218 histórica.','Seleção no treino, 45 configurações e esforço desigual. Pontos são vídeos; custo atual apenas dos cinco métodos reexecutados. T218 provém da busca anterior.'))
core=core.replace('{{FIG_CLASSICAL}}',figure('data/derived/detection/comparison_reports/classical_v1_20260911/comparacao_classicos_treino.png','F1 médio, F1 por vídeo e custo de detecção da melhor configuração da grade por família.','Busca limitada no treino, com esforço desigual e T218 previamente ajustado. Pontos representam vídeos; nenhuma promoção ou validação comparativa nesta etapa.'))
core=core.replace('{{FIG_VALIDACAO}}',figure('data/derived/detection/validation_reports/threshold_validation_v3_20260908/revision_02/validacao_threshold_completa.png','Comparação de T219 e T218 por vídeo completo de validação; cada candidato tem F1 maior em dois vídeos.','Figura da validação já conferida. O painel de diferenças usa escala ampliada e está identificado; o resultado é seleção, não confirmação.'))
core=core.replace('{{FIG_REFERENCIA}}',figure('data/derived/prediction/reference_reports/individual_trajectories_v1_20260908/trajetorias_individuais_treino.png','Cobertura, exclusões e contagem de janelas dos doze vídeos de treino.','Figura da preparação individual já conferida. Observações e janelas não são indivíduos independentes; todos os segmentos foram preservados.'))
core=core.replace('{{FIG_BASELINES}}',figure('data/derived/prediction/baseline_reports/prediction_baselines_v1_20260908/baselines_predicao_treino.png','ADE e FDE no horizonte de dez quadros, para persistência e velocidade constante, em cada vídeo e na média principal.','Figura dos baselines já conferida. Pesos iguais por ID dentro do vídeo e por vídeo. Resultados com GT no treino, sem fluxo e sem rastreamento estimado.'))
core=core.replace('{{FIG_FLOW}}',figure('data/derived/flow/reports/farneback_causal_smoke_v1_20260909/smoke_fluxo_causal.png','Campos aparentes do par 18→19 nos treinos 11 e 12, com diagnósticos do prefixo causal.','Figura do smoke conferido. Setas ampliadas 5× em grade de 24 pixels; não são trajetórias previstas. Barras descrevem médias de pares/trios com suporte por vídeo, sem inferência ou comparação de preditores.'))
core=core.replace('{{FIG_COMPACT}}',figure('data/derived/flow/reports/farneback_compact_benchmark_v1_20260909/benchmark_fluxo_compacto.png','Benchmark compacto de Farnebäck nos prefixos dos doze treinos: cobertura, reutilização e custo.','Figura derivada do benchmark conferido. Amostras únicas e usos em janelas são contagens diferentes; projeção de custo é provisória. Não há resultado de preditor, ADE/FDE ou avaliação em vídeos completos.'))

table='<table><thead><tr><th>Método fixo</th><th>ADE₁ = FDE₁</th><th>ADE₅</th><th>FDE₅</th><th>ADE₁₀</th><th>FDE₁₀</th></tr></thead><tbody>'
for row,label in zip(manifest['summary']['methods'],['Persistência','CV mediana5']):
    assert row['n_windows']==343776 and row['n_videos']==12
    table+='<tr><td>'+label+'</td>'+''.join('<td>'+fmt(row['macro_'+key])+'</td>' for key in ['ade_h1','ade_h5','fde_h5','ade_h10','fde_h10'])+'</tr>'
table+='</tbody></table>'
core=core.replace('{{TABELA_BASELINES}}',table)
refs='<ul>'+''.join(f'<li><a href="{escape(s["url"],quote=True)}">{escape(s["title"])}</a><span class="muted"> — {escape("; ".join(s["supports"]))}.</span></li>' for s in sources['primary_sources'])+'</ul>'
closing=read('closing.html').replace('{{FONTES_METRICAS}}',refs)
intro, core_rest = core.split('</section>', 1)
lab_part, closing_rest = closing.split('<section id="alinhamento"', 1)
lab_part = lab_part.replace('</section>', read('lab_extensions.html')+'</section>', 1)
body = intro+'</section>'+read('reading_guide.html')+core_rest+read('algorithms_deep.html')+read('walkthrough.html')+read('metrics.html')+lab_part+read('navigation.html')+read('artifacts_guide.html')+'<section id="alinhamento"'+closing_rest
excerpt_values, excerpt_sources = artifact_fragments(ROOT, compact_run, compact_manifest)
for key, value in excerpt_values.items():
    body = body.replace('{{'+key+'}}', value)
for key,value in compact_values.items():
    body=body.replace('{{'+key+'}}',value)
assert '{{' not in body and '}}' not in body
body=re.sub(r'(<table\b.*?</table>)',r'<div class="table-scroll" tabindex="0" role="region" aria-label="Tabela; role horizontalmente em telas pequenas">\1</div>',body,flags=re.S)

class Outline(HTMLParser):
    def __init__(self): super().__init__();self.stack=[];self.heads=[];self.words=[];self.h2=None;self.ids=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.append(attrs['id'])
        if tag=='section':self.stack.append(attrs.get('id',''))
        if tag=='h2':self.h2=[self.stack[0] if self.stack else attrs.get('id',''),'']
    def handle_endtag(self,tag):
        if tag=='h2' and self.h2:self.heads.append(self.h2);self.h2=None
        if tag=='section':self.stack.pop()
    def handle_data(self,data):
        self.words.append(data)
        if self.h2 is not None:self.h2[1]+=data

outline=Outline();outline.feed(body)
assert len(outline.ids)==len(set(outline.ids)), 'Duplicate body IDs'
heads=[]
for item in outline.heads:
    if item[0] not in [x[0] for x in heads]: heads.append(item)
toc=''.join(f'<a href="#{escape(id)}">{i:02d} · {escape(title)}</a>' for i,(id,title) in enumerate(heads,1))
words=len(re.findall(r'\b[\wÀ-ÿ]+\b',' '.join(outline.words)))
meta={'schema':'tcc_complete_report_v1','created_at':datetime.now(timezone.utc).isoformat(),'edition_date':'2026-09-11','scientific_state_date':'2026-09-11','flow_execution_commit':'16eecbb32b3edb4b4908ced344367670132a4cc1','flow_verifier_fix_commit':'0fccda8f663dc64a9ebc815b8cbaa60d5146fde1','flow_manifest_sha256':sha(FLOW_RUN/'manifest.json'),'flow_verification_sha256':sha(FLOW_QA),'reference_results_commit':'b55490f616c926cc937215372c0e2436dcbd437a','baseline_execution_commit':'5289c93e448c7e571ea92f30de3a7f5cb2c0d611','report_is_new_experiment':False,'read_original_video_sources':False,'new_model_runs':0,'baseline_manifest_sha256':sha(RUN/'manifest.json'),'baseline_verification_sha256':sha(qa),'figures':figures,'parts':[{'path':str((PARTS/name).relative_to(ROOT)),'sha256':sha(PARTS/name)} for name in ['core.html','closing.html','metrics.html','navigation.html','reading_guide.html','algorithms_deep.html','walkthrough.html','artifacts_guide.html','lab_extensions.html','report.css','report.js','lab_extensions.js','report_extensions.py','metrics_sources.json','folder_inventory.json']],'primary_sources':sources['primary_sources'],'folder_inventory_scope':inventory['scope'],'word_count_approx':words,'top_level_chapters':heads}
meta.update(compact_execution_commit='6110c44526c30f8f8f7a2fdeb276f7169d2fcd88',
    compact_benchmark_manifest_sha256=COMPACT_MANIFEST_SHA256,
    compact_benchmark_verification_sha256=COMPACT_QA_SHA256,
    compact_benchmark_source_hash=compact_manifest['source_hash'],
    latest_completed_milestone='classical_refinement_and_yolo_dataset_v1',
    level8_prediction_ablation_complete=False, documentary_excerpt_sources=excerpt_sources,
    synthetic_learning_widgets=['F1','ADE_FDE','causal_availability','bilinear_support'],
    documentation_only_expansion=False, planning_date='2026-09-11', next_proposed_milestone='classical_full_validation_and_yolo_training', executive_plan={'path':'docs/metodologia/CONTINUIDADE_EXPERIMENTAL_V1.md','sha256':sha(ROOT/'docs/metodologia/CONTINUIDADE_EXPERIMENTAL_V1.md')})

meta.update(classical_comparison={'manifest': 'data/tests/detection/classical_comparison/classical_detection_comparison_v1_operational_v2_20260911_batch__cfgb226c5dc/search/20260911T144742812472Z__2547109__cfgbecfe1d189e7__srcf14ede5a12__s42/manifest.json', 'manifest_sha256': '8a08f83d1b81be4dd2bae4b42bfea21bc08531d0e57ea9104f8693072ae606d0', 'verification': 'data/tests/detection/classical_comparison/classical_detection_comparison_v1_operational_v2_20260911_batch__cfgb226c5dc/search/verification_20260911.json', 'verification_sha256': 'c51f53f3d0a390a715460ce101c91a36e1d59e7e0c128e73ae12efc5da7da792', 'run_commit': '2547109', 'evaluations': 24768})
meta.update(classical_refinement={'summary': 'data/derived/detection/comparison_reports/classical_refinement_v1_20260911/revision_02/summary.json', 'summary_sha256': 'a17521606f2522d90689d93e77783990827e7b9ed2a22f95b3cb19260615f940', 'manifest': 'data/tests/detection/classical_refinement/classical_detection_refinement_v1_20260911_batch__cfgb8ebddfb/refinement/20260911T155556062315Z__ca68f16__cfgd1733d666bdc__srcf2ecb55da1__s42/manifest.json', 'manifest_sha256': '0c686f61f51af3129b89e878ba60ce2067e15c8c3bcceb478eee074f5e407e6b', 'verification': 'data/tests/detection/classical_refinement/classical_detection_refinement_v1_20260911_batch__cfgb8ebddfb/refinement/verification_20260911.json', 'verification_sha256': 'd82c58bff8d0ba8323ec1d43af23dc18f470c9da8f72c1c86d7aec14769f8118', 'run_commit': 'ca68f16', 'evaluations': 25920}, yolo_dataset={'manifest': 'data/datasets/yolo/materialized/yolo_dataset_v1_20260911__cfgfbd698da/preparation/20260911T161002135908Z__ca68f16__cfgf16cf2018592__srcf2ecb55da1__s42/manifest.json', 'manifest_sha256': 'e13f65035d1ae90dcb2337a8942022d70a45cfbb926a611df21b83add2c8bf42', 'verification': 'data/datasets/yolo/materialized/yolo_dataset_v1_20260911__cfgfbd698da/preparation/verification_20260911.json', 'verification_sha256': '0ad645d9cd20825984b70d5dab2b6d5dfd1a36970e10bd2a8b0129f81b2490be', 'run_commit': 'ca68f16', 'images': 23316, 'trained': False})
meta_json=json.dumps(meta,ensure_ascii=False).replace('</',r'<\/')
html='''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="Relatório completo e didático do TCC: objetivo, dados VISEM, algoritmos, métricas, resultados, pastas, evidências e próximos passos."><title>Entender o TCC — relatório completo</title><style>'''+read('report.css')+'''</style></head><body>
<a class="skip" href="#conteudo">Pular para o relatório</a><div class="layout"><aside class="sidebar"><span class="subbrand">UFU · Relatório de compreensão</span><a class="brand" href="#inicio">Análise e predição<br>de trajetórias</a><button id="menu" class="mobile-menu" type="button" aria-expanded="false" aria-controls="toc">Índice</button><label for="search">Encontrar um assunto</label><input id="search" type="search" placeholder="F1, threshold, pastas, fluxo…" autocomplete="off"><p class="search-hint">Busque por termo ou use Ctrl+F. Enter mostra os resultados; Esc limpa.</p><nav id="toc" aria-label="Capítulos do relatório">'''+toc+'''</nav><div class="links"><a href="mapa-tcc-didatico.html">Atlas do projeto ↗</a><a href="NAVEGACAO.md">Guia de navegação ↗</a><a href="../../README.md">Entrada do repositório ↗</a><a href="#fontes">Fontes e limites deste relatório</a></div></aside><div class="main-column"><header class="hero" id="inicio"><div class="eyebrow">Relatório completo · edição ampliada · continuidade revista em 11 de setembro de 2026</div><h1>Entender o TCC,<br>do objetivo à evidência.</h1><p class="subtitle">O que estamos investigando, como cada parte funciona, por que as decisões foram tomadas e o que falta para responder à pergunta científica.</p><div class="meta"><span>VISEM / VISEM-Tracking</span><span>Refinamento clássico e dataset YOLO conferidos</span><span>Hipótese com fluxo ainda pendente</span><span>Leitura local · figuras incorporadas</span></div><div class="toolbar"><a class="button primary" href="#visao">Começar a leitura</a><button id="expand" type="button">Expandir detalhes</button><button id="collapse" type="button">Recolher detalhes</button><button id="font-size" type="button" aria-pressed="false">Aumentar texto</button><button id="print" type="button">Imprimir / salvar PDF</button></div></header><div id="search-results" aria-live="polite" hidden></div><main id="conteudo">'''+body+'''</main><footer class="bottom">Relatório local do projeto “Análise e Predição de Trajetórias de Espermatozoides em Vídeos Microscópicos”. Estado científico de 11/09/2026. Os resultados completos, protocolos e histórico permanecem em seus arquivos de origem.</footer></div></div><script id="report-provenance" type="application/json">'''+meta_json+'''</script><script>'''+read('report.js')+'\n'+read('lab_extensions.js')+'''</script></body></html>'''
if OUT.exists() and 'compact_benchmark_manifest_sha256' not in OUT.read_text(encoding='utf-8'):
    snapshot=ROOT/'data/derived/project_audits/general_20260909/compact_flow_level8a_report_20260909'/('level7_before_compact_'+sha(OUT)[:16]+'.html')
    snapshot.parent.mkdir(parents=True,exist_ok=True)
    if not snapshot.exists():
        with snapshot.open('xb') as stream:
            stream.write(OUT.read_bytes())
html=html.replace('Nível 7 concluído e conferido</span>', 'Refinamento clássico e dataset YOLO conferidos</span>')
OUT.write_text(html,encoding='utf-8',newline='\n')
shortcut='''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="0;url=docs/projeto/RELATORIO_COMPLETO_TCC.html"><title>Relatório completo do TCC</title><script>location.replace('docs/projeto/RELATORIO_COMPLETO_TCC.html'+location.search+location.hash);</script><style>body{font:18px/1.6 system-ui;max-width:48rem;margin:12vh auto;padding:24px;color:#183b3d;background:#f6f5ee}a{color:#086a6d}</style></head><body><h1>Relatório completo do TCC</h1><p><a href="docs/projeto/RELATORIO_COMPLETO_TCC.html">Abrir o relatório: lógica do projeto, métricas, pastas, resultados e próximos passos</a>.</p><p>Continuidade revista em 11/09/2026. Refinamento clássico e dataset YOLO concluídos e conferidos em 11/09. Próximas etapas: validação completa e treinamento YOLO, antes da escolha da pipeline.</p><p><a href="MAPA_TCC_DIDATICO.html">Abrir o mapa didático</a></p></body></html>'''
shortcut=shortcut.replace('nível 7 concluído e conferido; hipótese com fluxo ainda pendente.',
    'marco 8a compacto concluído e conferido; extração completa e ablação com fluxo ainda pendentes.')
(ROOT/'RELATORIO_COMPLETO_TCC.html').write_text(shortcut,encoding='utf-8',newline='\n')
assert len(heads) == 19, heads
print(json.dumps({'report':str(OUT),'bytes':OUT.stat().st_size,'words_approx':words,'chapters':heads,'body_ids':len(outline.ids),'embedded_figures':len(figures)},ensure_ascii=False))
