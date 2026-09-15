"""Local documentary edits; no scientific execution or source-data changes."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[2]
parts = root / 'tmp/tcc_report'

def edit(relative, old, new):
    p = root / relative
    text = p.read_text(encoding='utf-8')
    assert old in text, (relative, old[:100])
    p.write_text(text.replace(old, new), encoding='utf-8', newline='\n')

edit('tmp/tcc_report/navigation.html',
     'O próximo marco precisa fechar o contrato causal e de cache antes do smoke real; a existência desses arquivos não afirma avaliação de fluxo no nível 6.',
     'Ao concluir o nível 6, ainda faltava fechar o contrato causal e de cache. Essa pendência foi resolvida pelo smoke do nível 7 e pela representação compacta do marco 8a, explicados acima. Agora falta medir e ajustar o custo antes da extração ampliada e da ablação; a existência das implementações legadas não demonstra sua avaliação científica.')

p = parts / 'walkthrough.html'
text = p.read_text(encoding='utf-8')
text, count = re.subn(r'<div class="table-scroll">(<table>.*?</table>)</div>', r'\1', text, flags=re.S)
assert count == 4
p.write_text(text, encoding='utf-8', newline='\n')

edit('tmp/tcc_report/report.css', '.controls{display:none}.muted', '.controls,.checkbox-label{display:none!important}.muted')

edit('docs/projeto/mapa-tcc-didatico.html',
     '09/09/2026 · <a href="NAVEGACAO.md">guia permanente</a>',
     '10/09/2026 · <a href="NAVEGACAO.md">guia permanente</a>')
edit('docs/projeto/mapa-tcc-didatico.html',
     'Lógica, métricas, pastas e próximos passos · 09/09/2026',
     '19 capítulos, exemplos e quatro laboratórios · 10/09/2026')
edit('docs/projeto/mapa-tcc-didatico.html',
     'A navegação foi revisada em 09/09/2026.',
     'A navegação foi revisada em 10/09/2026, sem alterar o estado científico de 09/09.')
edit('docs/projeto/mapa-tcc-didatico.html',
     '<main id="conteudo" class="content">',
     '''<main id="conteudo" class="content">
<section id="relatorio-ampliado" class="section">
<span class="kicker">Leitura orientada · edição de 10/09/2026</span>
<h2>Entenda o projeto, passo a passo</h2>
<p class="section-intro">O relatório ampliado reúne <strong>19 capítulos, cinco figuras científicas e quatro laboratórios didáticos</strong>. Explica a lógica dos algoritmos, as métricas, a função das pastas e o caminho entre um quadro e uma previsão. Exemplos inventados e registros reais estão identificados separadamente.</p>
<p><a href="RELATORIO_COMPLETO_TCC.html#guia-leitura">Escolher um roteiro de leitura</a> · <a href="RELATORIO_COMPLETO_TCC.html#algoritmos-detalhados">Entender os algoritmos</a> · <a href="RELATORIO_COMPLETO_TCC.html#exemplo-completo">Acompanhar um exemplo completo</a> · <a href="RELATORIO_COMPLETO_TCC.html#ler-artefatos">Ler os arquivos reais</a> · <a href="RELATORIO_COMPLETO_TCC.html#laboratorio">Experimentar os conceitos</a>.</p>
<div class="callout"><strong>Esta edição amplia a explicação.</strong><p>O último marco científico permanece o 8a, de 09/09: benchmark conferido, projeção de tempo acima do teto. A extração completa e a comparação de predição com/sem fluxo ainda estão pendentes. Consulte a seção seguinte para o resultado e seus limites.</p></div>
</section>''')
edit('MAPA_TCC_DIDATICO.html',
     'Relatório completo: lógica do TCC, métricas, pastas, resultados e próximos passos',
     'Relatório ampliado em 10/09/2026: 19 capítulos, algoritmos, métricas, pastas, exemplos e próximos passos')

# Keep the previous edition's checks and receipts unchanged.
(parts / 'qa_20260910_ampliado').mkdir(exist_ok=True)
p = parts / 'check_report_nivel8a.py'
text = p.read_text(encoding='utf-8').replace('qa_20260909_nivel8a', 'qa_20260910_ampliado')
text = text.replace("'RELATORIO_COMPLETO_TCC.html'):", "'RELATORIO_COMPLETO_TCC.html', 'docs/projeto/mapa-tcc-didatico.html', 'MAPA_TCC_DIDATICO.html'):")
text = text.replace("len(meta['top_level_chapters']) == 15", "len(meta['top_level_chapters']) == 19\n        assert meta['edition_date'] == '2026-09-10'\n        assert meta['scientific_state_date'] == '2026-09-09'\n        assert meta['documentation_only_expansion'] is True")
(parts / 'check_report_ampliado.py').write_text(text, encoding='utf-8', newline='\n')
p = parts / 'qa_report_nivel8a.cjs'
text = p.read_text(encoding='utf-8').replace('qa_20260909_nivel8a', 'qa_20260910_ampliado')
text = text.replace('structure.chapters,15', 'structure.chapters,19').replace("count(),15", "count(),19")
(parts / 'qa_report_ampliado.cjs').write_text(text, encoding='utf-8', newline='\n')
print('Documentary updates and separate QA scripts prepared.')
