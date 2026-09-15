from pathlib import Path
root = Path(__file__).resolve().parents[2]
parts = root/'tmp/tcc_report'
(parts/'qa_20260911_continuidade').mkdir(exist_ok=True)
text = (parts/'check_report_ampliado.py').read_text(encoding='utf-8')
text = text.replace('qa_20260910_ampliado','qa_20260911_continuidade').replace("meta['edition_date'] == '2026-09-10'", "meta['edition_date'] == '2026-09-11'")
(parts/'check_report_continuity.py').write_text(text,encoding='utf-8')
for name in ['AGENTS.md','docs/projeto/NAVEGACAO.md']:
    p=root/name; text=p.read_text(encoding='utf-8')
    substitutions={'prefixos8a':'prefixos do 8a','Origens19..59; alvos podem chegar69':'Origens 19..59; alvos podem chegar ao quadro 69',
      'teto120min':'teto de 120 min','plano8a':'plano 8a','projeção134,21min':'projeção de 134,21 min',
      'CLI de60quadros':'CLI de 60 quadros','continua8a de09/09':'continua sendo o 8a de 09/09'}
    for old,new in substitutions.items(): text=text.replace(old,new)
    p.write_text(text,encoding='utf-8',newline='\n')
