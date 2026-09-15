from pathlib import Path
import json

parts = Path(__file__).resolve().parent
source = (parts / 'qa_classical.cjs').read_text(encoding='utf-8')
source = source.replace('qa_20260911_classical', 'qa_20260911_classical_final')
source = source.replace("await page.screenshot({path:path.join(dir,`atlas_comparison_${label}.png`)});",
                        "await page.locator('#comparacao-classicos-atual').screenshot({path:path.join(dir,`atlas_comparison_${label}.png`)});")
assert "await page.locator('#comparacao-classicos-atual').screenshot" in source
marker = " await page.goto(pathToFileURL(path.resolve('MAPA_TCC_DIDATICO.html')).href+'#comparacao-classicos-atual');"
extra = '''
 const comparison=page.locator('#comparacao-classicos-20260911 table').nth(1);
 const scroll=await comparison.evaluate(el=>{el.scrollLeft=el.scrollWidth;return {left:el.scrollLeft,client:el.clientWidth,width:el.scrollWidth};});
 assert.ok(scroll.width>scroll.client && scroll.left>0,'mobile table horizontal scroll');
 await comparison.evaluate(el=>el.scrollIntoView({block:'start',behavior:'instant'}));
 await page.screenshot({path:path.join(dir,'report_comparison_mobile_right_columns.png')});
 await page.locator('#comparacao-classicos-20260911 details').first().evaluate(el=>el.open=true);
 const byVideo=page.locator('#comparacao-classicos-20260911 details').first();
 await byVideo.screenshot({path:path.join(dir,'report_by_video_mobile.png')});
'''
assert marker in source
source = source.replace(marker, extra+marker)
(parts / 'qa_classical_final.cjs').write_text(source, encoding='utf-8')
source = (parts / 'check_report_classical.py').read_text(encoding='utf-8').replace('qa_20260911_classical','qa_20260911_classical_final')
(parts / 'check_report_classical_final.py').write_text(source, encoding='utf-8')
(parts / 'qa_20260911_classical_final').mkdir(exist_ok=True)
with (parts / 'qa_20260911_classical' / 'visual_review.json').open('x', encoding='utf-8') as stream:
    json.dump({'status':'superseded_for_visual_scope', 'reason':'Automated checks passed, but atlas viewport screenshots did not capture the intended comparison section. The final check captures the actual section and verifies horizontal table scrolling. Added explanatory mobile-table hint in the report.', 'follow_up':'tmp/tcc_report/qa_20260911_classical_final'},stream,ensure_ascii=False,indent=2)
