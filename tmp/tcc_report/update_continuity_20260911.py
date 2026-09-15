"""Publish the prospective roadmap locally, preserving the preceding edition."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
PARTS = ROOT / 'tmp/tcc_report'
DEST = ROOT / 'data/derived/project_audits/general_20260911/continuity_plan_20260911'
DEST.mkdir(parents=True, exist_ok=True)
names = ['docs/projeto/RELATORIO_COMPLETO_TCC.html','RELATORIO_COMPLETO_TCC.html',
 'docs/projeto/mapa-tcc-didatico.html','MAPA_TCC_DIDATICO.html','AGENTS.md',
 'docs/projeto/NAVEGACAO.md','tmp/tcc_report/core.html','tmp/tcc_report/closing.html',
 'tmp/tcc_report/navigation.html','tmp/tcc_report/reading_guide.html','tmp/tcc_report/build_report.py']
records=[]
for name in names:
    source=ROOT/name; raw=source.read_bytes(); target=DEST/'before'/name
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as stream: stream.write(raw)
    records.append({'path':name,'snapshot':target.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(raw).hexdigest()})
with (DEST/'before_manifest.json').open('x',encoding='utf-8') as stream:
    json.dump({'purpose':'Preserve edition before prospective planning update','files':records},stream,ensure_ascii=False,indent=2)

def edit(name, old, new):
    p=ROOT/name; text=p.read_text(encoding='utf-8'); assert old in text,(name,old[:80])
    p.write_text(text.replace(old,new),encoding='utf-8',newline='\n')

edit('tmp/tcc_report/core.html','<h3>Resolver o custo da extração</h3><p>Separar os tempos internos do laço e registrar uma avaliação operacional controlada. A projeção excedeu o teto de tempo; os vídeos completos ainda não foram liberados.</p>',
 '<h3>Comparar previsão com e sem fluxo</h3><p>Plano revisto em 11/09: usar as 10.848 janelas já conferidas para a primeira ablação exploratória, sob novo contrato. Avançar também no rastreamento e no ambiente aprendido.</p>')
p=PARTS/'closing.html'; text=p.read_text(encoding='utf-8')
text,n=re.subn(r'<section id="proximos".*?</section>',(PARTS/'continuity_roadmap.html').read_text(encoding='utf-8'),text,flags=re.S)
assert n==1; p.write_text(text,encoding='utf-8',newline='\n')
edit('tmp/tcc_report/navigation.html','Agora falta medir e ajustar o custo antes da extração ampliada e da ablação;',
 'O plano de 11/09 prioriza a primeira ablação nos derivados já disponíveis; extração completa e memória terão protocolo próprio;')
edit('tmp/tcc_report/reading_guide.html','É um indicador de planejamento que exige investigar o custo antes de autorizar a escala; a RAM completa também não foi certificada.',
 'É o resultado da regra operacional anterior. Em 11/09 o pesquisador retirou tempo como impedimento permanente; uma nova extração precisa de plano próprio e controle de memória, sem reescrever esse resultado. A primeira ablação pode usar os derivados já disponíveis.')
p=PARTS/'reading_guide.html'; text=p.read_text(encoding='utf-8')
start=text.index('  <p>A próxima etapa experimental proposta é')
end=text.index('</section>',start)
text=text[:start]+'''  <p>A próxima entrega proposta é a <strong>primeira ablação exploratória nas 10.848 janelas dos 12 prefixos já conferidos</strong>. Ela compara CV mediana5 e a variante causal com fluxo, com controle secundário pelo último deslocamento. Os campos já existem; faltam o contrato próprio e o leitor/executor autenticado, antes de calcular erros.</p>
  <p>O resultado será descritivo no treino e não representa todos os vídeos completos. Em paralelo, preparar avaliação dos rastreadores e ambiente aprendido. A ampliação posterior terá memória e retenção planejadas; não depende de reduzir a projeção ao teto histórico de 120 minutos. Consulte <a href="#proximos">a sequência atualizada</a> e o <a href="../metodologia/CONTINUIDADE_EXPERIMENTAL_V1.md">plano executivo de 11/09</a>.</p>
'''+text[end:]
p.write_text(text,encoding='utf-8',newline='\n')
edit('tmp/tcc_report/build_report.py','Sua projeção excedeu o teto de tempo; a extração completa aguarda investigação de custo e novo plano operacional.',
 'Sua projeção excedeu o teto histórico de tempo. O plano de 11/09 prioriza uma primeira ablação nos derivados disponíveis e exige plano próprio para ampliar a extração.')
edit('tmp/tcc_report/build_report.py',"'edition_date':'2026-09-10'","'edition_date':'2026-09-11'")
edit('tmp/tcc_report/build_report.py','edição ampliada de 10 de setembro de 2026','edição ampliada · continuidade revista em 11 de setembro de 2026')
edit('tmp/tcc_report/build_report.py','Edição ampliada de 10/09/2026. Estado científico de 09/09: marco 8a concluído; custo ampliado e ablação ainda pendentes.',
 'Continuidade revista em 11/09/2026. Estado científico de 09/09: marco 8a concluído. Próxima entrega proposta: ablação exploratória nos derivados disponíveis.')
edit('tmp/tcc_report/build_report.py','documentation_only_expansion=True)',
 "documentation_only_expansion=True, planning_date='2026-09-11', next_proposed_milestone='exploratory_prediction_ablation_on_existing_compact_prefixes', executive_plan={'path':'docs/metodologia/CONTINUIDADE_EXPERIMENTAL_V1.md','sha256':sha(ROOT/'docs/metodologia/CONTINUIDADE_EXPERIMENTAL_V1.md')})")

notice='''## Continuidade vigente — 11/09/2026

O [plano executivo](docs/metodologia/CONTINUIDADE_EXPERIMENTAL_V1.md) prioriza
a primeira ablação exploratória nas 10.848 janelas dos 12 prefixos8a já
conferidos, sem repetir a extração. Antes de ADE/FDE, registrar contrato/YAML e
implementar leitor autenticado e executor: CV mediana5 versus CV causal com
fluxo, com controle secundário cv_last. Origens19..59; alvos podem chegar69,
somente para avaliação. Não há resultado novo ou promoção.

O pesquisador retirou em 11/09 o tempo como impedimento à continuidade.
O teto120min permanece histórico no plano8a, cuja projeção134,21min não passou.
Novos planos podem monitorar tempo sem esse corte. Não reescrever a run/YAML,
nem ampliar pela CLI de60quadros; preservar RAM, armazenamento e completude.
Otimização de velocidade não antecede obrigatoriamente a primeira ablação.
Avançar em paralelo no contrato HOTA/rastreadores e ambiente aprendido.
Esse roteiro substitui as indicações abaixo de instrumentação como próximo
marco obrigatório. O último resultado científico continua8a de09/09.

'''
edit('AGENTS.md','## Navegação e retomada',notice+'## Navegação e retomada')
edit('AGENTS.md','O próximo marco é medir e ajustar o custo antes da extração ampliada e ablação.',
 'O próximo marco é registrar e executar a ablação exploratória nos derivados disponíveis, conforme o plano de 11/09.')
guide_notice=notice.replace('(docs/metodologia/CONTINUIDADE_EXPERIMENTAL_V1.md)','(../metodologia/CONTINUIDADE_EXPERIMENTAL_V1.md)')
edit('docs/projeto/NAVEGACAO.md','Atualizado em 2026-09-10.',guide_notice+'Atualizado em 2026-09-11.')
edit('docs/projeto/NAVEGACAO.md','O próximo marco deve medir e ajustar o custo antes da extração completa\ne da ablação com/sem fluxo.',
 'O plano de 11/09 prioriza a primeira ablação nos derivados disponíveis, com\nnovo contrato; a extração completa terá plano próprio.')
edit('docs/projeto/NAVEGACAO.md','atual é o nível 7, smoke causal de Farnebäck concluído e conferido,\n   conforme a seção 16.',
 'atual é o marco 8a, benchmark compacto concluído e conferido,\n   conforme a seção 17. A continuidade vigente consta no início deste guia.')

atlas_notice='''<section id="continuidade-20260911" class="section">
<span class="kicker">Planejamento atualizado · 11/09/2026</span><h2>Próxima entrega: comparar previsões com e sem fluxo</h2>
<p class="section-intro">Usar as 10.848 janelas dos 12 prefixos já conferidos, sob novo contrato e executor. Não repetir a extração. A primeira comparação será exploratória no treino; rastreamento real e preparação dos modelos aprendidos avançam em paralelo.</p>
<p>O tempo deixou de ser impedimento permanente para novas etapas. A projeção de 134,21 minutos continua reprovada frente ao teto histórico de 120; a extração completa exige outro plano com memória e recursos controlados. Nenhuma nova avaliação foi executada nesta revisão de continuidade.</p>
<p><a href="RELATORIO_COMPLETO_TCC.html#proximos">Ler a sequência no relatório</a> · <a href="../metodologia/CONTINUIDADE_EXPERIMENTAL_V1.md">Plano executivo completo</a>.</p></section>
'''
edit('docs/projeto/mapa-tcc-didatico.html','<section id="relatorio-ampliado"',atlas_notice+'<section id="relatorio-ampliado"')
edit('docs/projeto/mapa-tcc-didatico.html','<strong>O próximo passo é investigar o laço; o nível 8 inteiro continua aberto.</strong>',
 '<strong>Roteiro indicado em 09/09; veja a continuidade revista em 11/09 no início.</strong>')
edit('MAPA_TCC_DIDATICO.html','Próximo passo: separar os custos internos do laço e registrar uma avaliação operacional controlada, sem alterar o teto retroativamente.',
 'Continuidade revista em 11/09: preparar a primeira ablação nas 10.848 janelas já conferidas, sem nova extração. Novos planos podem monitorar tempo sem o teto histórico; a memória continua sob controle.')
print('Roadmap, report components, atlas and local navigation updated; preceding edition preserved.')
