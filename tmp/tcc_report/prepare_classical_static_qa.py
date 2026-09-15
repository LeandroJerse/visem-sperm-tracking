from pathlib import Path
parts = Path(__file__).resolve().parent
source = (parts / 'check_report_continuity.py').read_text(encoding='utf-8')
source = source.replace("meta['scientific_state_date'] == '2026-09-09'", "meta['scientific_state_date'] == '2026-09-11'")
source = source.replace("meta['documentation_only_expansion'] is True", "meta['documentation_only_expansion'] is False")
source = source.replace('qa_20260911_continuidade', 'qa_20260911_classical')
(parts / 'qa_20260911_classical').mkdir(exist_ok=True)
(parts / 'check_report_classical.py').write_text(source, encoding='utf-8')
