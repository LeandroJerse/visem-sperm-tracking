from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[2]
def polish(s):
    for word in ['nível','Nível','seção','Seção','vídeo','vídeos','treinos','origem','quadros','nominal','total','amostrado','foram','contra','máxima','diferença','par','Smoke','smoke','conferiu','Em']:
        s=re.sub(r'\b('+word+r')(?=\d)',r'\1 ',s)
    s=re.sub(r'(?<=\d)(MiB|GiB|px|s)\b',r' \1',s)
    s=re.sub(r'(?<=[,;:])(?=\d)',lambda m:' ' if m.string[m.start()-1] in ';:' else '',s)
    s=s.replace('no12','no 12').replace('é18','é 18').replace('QA190','QA 190')
    s=s.replace('Suite selecionada','Suíte selecionada')
    return s
for p,marker in [('docs/metodologia/FLUXO_CAUSAL_V1.md','## Resultados do smoke'),('docs/projeto/DIARIO.md','## 2026-09-09 — nível 7 concluído')]:
    path=ROOT/p;s=path.read_text(encoding='utf-8')
    if 'DIARIO' in p:
        a,b=s.split('## 2026-09-09 — compatibilidade',1);s=polish(a)+'## 2026-09-09 — compatibilidade'+b
    else:
        a,b=s.split(marker,1);s=a+polish(marker+b)
        s=s.replace('Validação/teste originais e runs anteriores não foram reabertos.', 'Fontes originais de validação/teste não foram abertas; runs anteriores\nforam preservadas.')
        s=s.replace('de novas extrações; não há autorização metodológica implícita para varrer\nparâmetros com base nos diagnósticos deste smoke.', 'de novas extrações. Um benchmark prospectivo de custo e uma política de\narmazenamento precederão a expansão: campos e amostras sobrepostas poderão\nser reutilizados por chave, com auditabilidade definida. Não selecionar novos\nparâmetros com base nos diagnósticos deste smoke sem protocolo próprio.')
    path.write_text(s,encoding='utf-8',newline='\n')
for p in ['AGENTS.md','docs/projeto/NAVEGACAO.md','docs/algoritmos/fluxo/farneback.md','docs/projeto/MATRIZ_EXPERIMENTOS.md','monografia/README.md']:
    path=ROOT/p;s=path.read_text(encoding='utf-8')
    # Exact lexical substitutions do not affect machine-readable identifiers or paths.
    for old,new in [('nível7','nível 7'),('Nível7','Nível 7'),('seção16','seção 16'),('Seção16','Seção 16'),('seção15','seção 15'),('Suíte selecionada:1','Suíte selecionada: 1'),('Suite selecionada:1','Suíte selecionada: 1'),('conferiu190','conferiu 190'),('QA190','QA 190'),('origem19','origem 19'),('quadros0','quadros 0'),('treinos11','treinos 11'),('Smoke11','Smoke 11'),('smoke11','smoke 11'),('Em09','Em 09'),('em11','em 11'),('de08','de 08'),('conferidos854','conferidos 854'),('diferença8','diferença 8'),('Conferência:190','Conferência: 190'),('SHA256:`','SHA256: `'),('t19','t=19'),('pares0','pares 0'),('são2 vídeos','são 2 vídeos'),('traz19','traz 19'),('confundir68','confundir 68')]: s=s.replace(old,new)
    if p.endswith('NAVEGACAO.md'):
        s=s.replace('atual é o nível 6, bateria dos baselines causais concluída e conferida,\n   conforme a seção 15.', 'atual é o nível 7, smoke causal de Farnebäck concluído e conferido,\n   conforme a seção 16. Os baselines do nível 6 permanecem na seção 15.')
    path.write_text(s,encoding='utf-8',newline='\n')
print('Spacing, continuation instructions and source-access wording reviewed.')
