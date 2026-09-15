from pathlib import Path
import json
parts=Path(__file__).resolve().parent
source=(parts/'qa_classical_final.cjs').read_text(encoding='utf-8')
source=source.replace('qa_20260911_classical_final','qa_20260911_classical_final_retry1')
source=source.replace('el=>{el.scrollLeft=el.scrollWidth;return {left:el.scrollLeft,client:el.clientWidth,width:el.scrollWidth};}',
                      'el=>{const container=el.closest(".table-scroll");container.scrollLeft=container.scrollWidth;return {left:container.scrollLeft,client:container.clientWidth,width:container.scrollWidth};}')
assert 'const container=el.closest' in source
(parts/'qa_classical_final_retry1.cjs').write_text(source,encoding='utf-8')
(parts/'qa_20260911_classical_final_retry1').mkdir(exist_ok=True)
source=(parts/'check_report_classical_final.py').read_text(encoding='utf-8').replace('qa_20260911_classical_final','qa_20260911_classical_final_retry1')
(parts/'check_report_classical_final_retry1.py').write_text(source,encoding='utf-8')
with (parts/'qa_20260911_classical_final'/'failure.json').open('x',encoding='utf-8') as stream:
    json.dump({'status':'failed','error':'AssertionError: mobile table horizontal scroll', 'cause':'QA inspected the table element; horizontal scrolling belongs to its .table-scroll wrapper. Report structure and static checks passed.','report_changed_for_retry':False,'follow_up':'tmp/tcc_report/qa_20260911_classical_final_retry1'},stream,ensure_ascii=False,indent=2)
