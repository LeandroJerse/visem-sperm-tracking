"""Record completed, independently checked level-six results without editing runs."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = Path('data/tests/prediction/baselines/prediction_baselines_v1__cfgc874ef20/development/20260908T202138821137Z__5289c93__cfg11aeec0be9f3__srcf738122f1f__s42')
QA = RUN.parent / 'verification_20260908.json'
FIG = Path('data/derived/prediction/baseline_reports/prediction_baselines_v1_20260908')
m = json.loads((ROOT / RUN / 'manifest.json').read_text())
q = json.loads((ROOT / QA).read_text())
mh = hashlib.sha256((ROOT / RUN / 'manifest.json').read_bytes()).hexdigest()
qh = hashlib.sha256((ROOT / QA).read_bytes()).hexdigest()
assert m['status'] == 'complete' and m['git_dirty'] is False and m['git_sha'] == '5289c93'
assert q['status'] == 'passed' and q['run_manifest_sha256'] == mh
assert json.loads((ROOT / FIG / 'visual_review.json').read_text())['status'] == 'passed'
methods = m['summary']['methods']
rows = list(csv.DictReader((ROOT / RUN / 'video_metrics.csv').open(encoding='utf-8', newline='')))
by_pair = {(r['video_id'], r['configuration_id']): r for r in rows}

def pt(value, decimals=6):
    return f'{value:,.{decimals}f}'.replace(',', '_').replace('.', ',').replace('_', '.')

pending = {}
def replace(path, old, new):
    p = ROOT / path
    raw = pending.get(p, p.read_bytes())
    newline = '\r\n' if b'\r\n' in raw else '\n'
    text = raw.decode('utf-8').replace('\r\n', '\n')
    assert text.count(old) == 1, (path, old[:85], text.count(old))
    pending[p] = text.replace(old, new).replace('\n', newline).encode('utf-8')

def append(path, text):
    p = ROOT / path
    raw = pending.get(p, p.read_bytes())
    newline = '\r\n' if b'\r\n' in raw else '\n'
    assert text.splitlines()[0].encode() not in raw
    pending[p] = raw.rstrip() + (newline * 2 + text.rstrip().replace('\n', newline) + newline).encode('utf-8')

replace('docs/metodologia/BASELINES_PREDICAO_V1.md',
    'com identificador `prediction_baselines_v1_20260908`. Ainda não há resultados\nde predição deste marco. Implementação, testes, registro do código e execução\ndeverão respeitar as regras abaixo.',
    'com identificador `prediction_baselines_v1_20260908`. Código e plano foram\nregistrados em `5289c93` antes da bateria. A execução e a conferência independente\nforam concluídas; os [resultados](#resultados-da-bateria--08092026) estão ao fim\ndeste documento. As regras prospectivas abaixo foram preservadas.')

result = f'''## Resultados da bateria — 08/09/2026

**Nível 6 concluído: duas referências fixas no treino, sem seleção de modelo.**
A primeira execução terminou sob `5289c93`, Git limpo, após **1.362 testes
aprovados em 144,75 s**. A conferência independente também passou na primeira
execução. Nenhuma fonte original foi reaberta, nem pixels, detector, tracker
ou fluxo foram processados nesta bateria. Validação e teste não foram avaliados.

Cada método consumiu todas as **343.776 janelas** da referência, em 12 vídeos:
**687.552 avaliações de janela**, com **6.875.520 posições futuras** exportadas.
As janelas cobrem 606 dos 669 IDs individuais originais e 623 dos 725 segmentos.
Os 63 IDs sem janela e os 102 segmentos sem janela continuam registrados no
pai; não receberam erro zero e não foram confundidos com falha dos preditores.

### Erros com a agregação principal

Média das janelas de cada ID original, depois pesos iguais para os IDs do
vídeo e para os 12 vídeos. Unidades: pixels da imagem original. As casas
decimais da tabela são apresentação; os CSVs conservam a precisão processada.

| Método fixo | ADE₁ = FDE₁ | ADE₅ | FDE₅ | ADE₁₀ | FDE₁₀ |
|---|---:|---:|---:|---:|---:|
'''
for row, label in zip(methods, ('Persistência', 'Velocidade constante, mediana5')):
    result += '| ' + label + ' | ' + ' | '.join(pt(row['macro_' + k]) for k in ('ade_h1','ade_h5','fde_h5','ade_h10','fde_h10')) + ' |\n'
result += '''
Na média principal, a velocidade constante tem ADE₁₀ menor em 0,753944 px
e FDE₁₀ menor em 0,845377 px. A diferença não é uniforme: o ADE₁₀ é menor
em 9/12 vídeos e o FDE₁₀ em 7/12. Em 11/21/23, ambos os erros são maiores
com extrapolação. Em 12/15, o ADE₁₀ é menor, mas o FDE₁₀ é maior. Esses
contrastes são descrições do treino; não demonstram superioridade geral,
não selecionam um método e não autorizam ajustar parâmetros retrospectivamente.

| Vídeo | Persistência ADE₁₀ | CV ADE₁₀ | Persistência FDE₁₀ | CV FDE₁₀ |
|---|---:|---:|---:|---:|
'''
for video in m['summary']['video_ids']:
    p, c = (by_pair[(video, method)] for method in ('persistence', 'cv_median5'))
    result += f'| {video} | ' + ' | '.join(pt(float(r[k])) for r,k in ((p,'ade_h10'),(c,'ade_h10'),(p,'fde_h10'),(c,'fde_h10'))) + ' |\n'
result += '''
### Sensibilidade aos pesos e duração dos horizontes

A agregação secundária dá peso igual às janelas dentro de cada vídeo e
depois peso igual aos vídeos. Os IDs com mais janelas contribuem mais nesse
estimando, enquanto a regra principal dá a cada ID avaliado o mesmo peso.

| Método fixo | ADE₁ = FDE₁ | ADE₅ | FDE₅ | ADE₁₀ | FDE₁₀ |
|---|---:|---:|---:|---:|---:|
'''
for row, label in zip(methods, ('Persistência', 'Velocidade constante, mediana5')):
    result += '| ' + label + ' | ' + ' | '.join(pt(row['macro_window_weighted_' + k]) for k in ('ade_h1','ade_h5','fde_h5','ade_h10','fde_h10')) + ' |\n'
result += f'''
Os dois agregados não devem ser misturados ou escolhidos conforme o resultado.
A diferença entre eles mostra que a distribuição das janelas por ID afeta
o resumo; não identifica, por si só, a causa dos erros de cada trajetória.

O FPS nominal exportado é 48 no vídeo 35, 50 no 82 e 49 nos demais. Dez
quadros correspondem, respectivamente, a 0,208333 s, 0,200000 s e 0,204082 s.
As 20 posições históricas abrangem 19 intervalos; nenhuma reamostragem foi
feita. Não se trata de um horizonte físico idêntico em todos os vídeos.

### Custo e conferência independente

A bateria levou **54,191753 s**, com RSS amostrado máximo de **199,027 MiB**
em 1.376 amostras. Foram gravados **419.207.751 bytes** antes do manifesto final
(399,788 MiB). O cálculo em lote dos preditores somou aproximadamente 0,098467 s
para persistência e 0,317673 s para CV; esses tempos excluem leitura, métricas
e gravação. Não são latência de uma pipeline de vídeo nem benchmark de FPS.
GPU não foi usada; os campos de VRAM do monitor são indisponíveis, não zero medido.

A conferência reconstituiu todas as previsões e métricas densas usando somente
JSON/CSV derivados e biblioteca padrão, sem importar a implementação do projeto.
Conferiu **{q['files_verified']} arquivos**, sendo 99 artefatos novos, seu manifesto
e 87 arquivos da referência e de sua certificação; realizou
**{pt(q['comparisons'],0)} comparações**, das quais **{pt(q['numeric_comparisons'],0)} numéricas**,
em **{pt(q['elapsed_seconds'],4)} s**. Contagens, parâmetros, identidades e índices
foram comparados exatamente; floats usam tolerância absoluta 1e-9 e relativa
1e-12. A maior diferença numérica observada foi {q['max_absolute_difference']:.3g}.
Históricos e alvos foram reconstruídos, com hashes binários conferidos nos dois
métodos; não houve nova filtragem de janelas. Isso verifica a implementação e
os artefatos, sem criar uma avaliação estatisticamente independente do treino.

| Evidência local | Caminho |
|---|---|
| Manifesto completo | [manifest.json](../../{RUN.as_posix()}/manifest.json) |
| Resumo principal e secundário | [summary.json](../../{RUN.as_posix()}/summary.json) |
| Todos os pares método–vídeo | [video_metrics.csv](../../{RUN.as_posix()}/video_metrics.csv) |
| Diferenças CV menos persistência | [paired_video_metrics.csv](../../{RUN.as_posix()}/paired_video_metrics.csv) |
| Previsões, métricas por janela e ID | [by_video/](../../{RUN.as_posix()}/by_video/) |
| Conferência independente | [verification_20260908.json](../../{QA.as_posix()}) |
| Figura por vídeo | [PNG](../../{FIG.as_posix()}/baselines_predicao_treino.png) e [SVG](../../{FIG.as_posix()}/baselines_predicao_treino.svg) |
| Proveniência e revisão visual | [manifest.json](../../{FIG.as_posix()}/manifest.json) e [visual_review.json](../../{FIG.as_posix()}/visual_review.json) |

SHA256 do manifesto: `{mh}`.
SHA256 da conferência: `{qh}`.
Fonte de código da run: `{m['source_hash']}`.
A figura PNG foi inspecionada visualmente; o SVG vem da mesma renderização.
O mapa HTML e os links foram conferidos estaticamente, sem validação de navegador.

### Continuidade

O próximo marco é registrar e verificar o contrato causal de características
locais de Farnebäck: pares somente até a origem, posição e sistema de
coordenadas corretos, máscara e validade explícitas, ausências preservadas e
coorte comum para os métodos com e sem fluxo. Primeiro casos sintéticos e
smoke limitado no treino; uma extração ampla dependerá de protocolo e orçamento.
Não foram executados fluxo, HOTA, preditores aprendidos ou avaliação fim a fim.
A hipótese principal e o desenho confirmatório continuam pendentes.
'''
append('docs/metodologia/BASELINES_PREDICAO_V1.md', result)

replace('README.md', '   e 343.776 janelas; o próximo passo implementa seu consumo pelos preditores.',
    '   e 343.776 janelas. A [comparação fixa de persistência e velocidade constante](docs/metodologia/BASELINES_PREDICAO_V1.md#resultados-da-bateria--08092026)\n   também foi concluída e conferida nessas janelas, somente no treino com GT.\n   O próximo marco verifica as entradas causais de fluxo aparente local.')
replace('docs/README.md', '## Marco atual: linha de base e referência individual',
    '## Marco atual: baselines de predição conferidos no treino')

for file, label, ade, fde in [('persistencia.md','persistência',3.890963962031686,6.619750557023345),('velocidade_constante.md','CV mediana5',3.1370196218604183,5.774373140556036)]:
    path='docs/algoritmos/predicao/'+file
    replace(path, 'Ainda não há pasta de runs específica deste método; o link abre a área do domínio.',
        'A primeira bateria fixa está em `data/tests/prediction/baselines/`, com\nsubpastas por vídeo e método. Os [resultados conferidos](../../metodologia/BASELINES_PREDICAO_V1.md#resultados-da-bateria--08092026)\nligam os artefatos e a figura; as entradas genéricas acima continuam disponíveis.')
    old = 'Resultado da execução v1: **pendente**.' if file=='persistencia.md' else 'Resultado da execução v1: **pendente**; nenhum híbrido é avaliado nesta bateria.'
    replace(path, old, f'Resultado v1 conferido: **ADE₁₀ {pt(ade)} px; FDE₁₀ {pt(fde)} px**,\ncom peso igual por ID original dentro do vídeo e por vídeo. São 343.776 janelas\ndos 12 vídeos de treino, sob `5289c93`; não é avaliação com tracking ou fluxo.\nA bateria não seleciona hiperparâmetros nem promove o método para uso final.')

replace('docs/algoritmos/predicao/README.md', '## Referência individual preparada, sem avaliação de modelos',
    '## Referência individual e baselines fixos de treino')
replace('docs/algoritmos/predicao/README.md',
    'independentemente. São índices comuns de elegibilidade, ainda sem resultados\ndos preditores. O executor antigo de CSV não constitui automaticamente essa\ncomparação: precisa consumir os segmentos, separar alvos de entradas e\nusar ADE denso em 1..H. Os 102 segmentos curtos foram preservados.',
    'independentemente. Os 102 segmentos sem janelas foram preservados. A\n[bateria fixa v1](../../metodologia/BASELINES_PREDICAO_V1.md#resultados-da-bateria--08092026)\navaliou persistência e CV mediana5 em todas essas janelas, com conferência\nintegral dos CSVs. O executor próprio usa históricos separados dos alvos e\nADE denso em 1..H, com posições float64 em formato largo. O executor genérico\nde CSV mantém seu contrato histórico; não certifica automaticamente essa\ncomparação. Fluxo, preditores aprendidos e cenário com tracking estão pendentes.')

replace('docs/projeto/MATRIZ_EXPERIMENTOS.md',
    '| Próximo marco | Consumir índices comuns nos baselines de predição com ADE denso e entradas causais; contrato HOTA próprio ainda pendente |',
    '| Baselines de predição no treino | Concluídos em 5289c93: persistência e CV mediana5 nas mesmas 343.776 janelas; conferência integral aprovada |\n| Próximo marco | Contrato e smoke de características causais de Farnebäck; contrato HOTA próprio ainda pendente |')
replace('docs/projeto/MATRIZ_EXPERIMENTOS.md',
    'e 343.776 janelas. Isso prepara os dados; as colunas de avaliação dos modelos\nabaixo continuam pendentes. Os 102 segmentos sem janela foram preservados.',
    'e 343.776 janelas. Os 102 segmentos sem janela foram preservados. A\n[bateria fixa v1](../metodologia/BASELINES_PREDICAO_V1.md#resultados-da-bateria--08092026)\nconcluiu persistência e CV mediana5 nessas mesmas janelas; a conferência\nindependente aprovou previsões, métricas e agregações. Isso é desenvolvimento\ndescritivo com GT de treino, sem tuning, validação, seleção de vencedor ou fluxo.')
old='''| Algoritmo | Código | Analítico/sintético | GT: tuning/val | Tracker: tuning/val | Congelar | Teste | 5-fold | Aplicar 65 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Persistência | ✓ | ✓ | — | — | — | — | — | — |
| Velocidade constante | ✓ | ✓ | — | — | — | — | — | — |
| Kalman | ✓ | ✓ | — | — | — | — | — | — |
| Filtro de partículas | ✓ | ✓ | — | — | — | — | — | — |
| LSTM sem fluxo | ✓ | API; treino pendente | — | — | — | — | — | — |
| LSTM com fluxo | ✓ | API; treino pendente | — | — | — | — | — | — |
| Híbridos clássicos flow-aware | ✓ | ✓ | — | — | — | — | — | — |'''
new='''| Algoritmo | Código | Analítico/sintético | GT: desenvolvimento fixo | GT: tuning/val | Tracker: tuning/val | Congelar | Teste | 5-fold | Aplicar 65 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Persistência | ✓ | ✓ | ✓ v1 | — | — | — | — | — | — |
| Velocidade constante | ✓ | ✓ | ✓ mediana5 v1 | — | — | — | — | — | — |
| Kalman | ✓ | ✓ | — | — | — | — | — | — | — |
| Filtro de partículas | ✓ | ✓ | — | — | — | — | — | — | — |
| LSTM sem fluxo | ✓ | API; treino pendente | — | — | — | — | — | — | — |
| LSTM com fluxo | ✓ | API; treino pendente | — | — | — | — | — | — | — |
| Híbridos clássicos flow-aware | ✓ | ✓ | — | — | — | — | — | — | — |'''
replace('docs/projeto/MATRIZ_EXPERIMENTOS.md',old,new)
replace('docs/metodologia/PROTOCOLO.md',
    'é preparada somente no treino. O desenho confirmatório continua pendente.',
    'foi preparada e conferida somente no treino. A [comparação fixa dos baselines](BASELINES_PREDICAO_V1.md#resultados-da-bateria--08092026)\nconcluiu persistência e CV mediana5 nas 343.776 janelas comuns, sob `5289c93`,\ncom conferência independente integral. A hipótese com fluxo e o desenho\nconfirmatório continuam pendentes.')
replace('docs/metodologia/PROTOCOLO.md',
    'erros somente nos pontos 1/5/10 é outro estimando. Esses controles ainda\nprecisam ser materializados e testados, conforme a revisão geral.',
    'erros somente nos pontos 1/5/10 é outro estimando. A [bateria fixa v1](BASELINES_PREDICAO_V1.md)\nmaterializou e testou esses controles para persistência e CV com GT, inclusive\no consumo exato do índice e a precisão de exportação. O executor genérico e\nas variantes com fluxo ainda exigem contratos próprios. A próxima etapa\nverificará pares de imagens, coordenadas e disponibilidade causal do fluxo\nantes de formar a coorte comum da ablação.')

append('docs/projeto/DIARIO.md', f'''## 2026-09-08 — nível 6 concluído: baselines fixos no treino

Primeira execução completa em `5289c93`, Git limpo e reconferido no encerramento,
54,191753 s, RSS amostrado 199,027 MiB e 419.207.751 bytes antes do manifesto.
Persistência e CV mediana5 consumiram as mesmas 343.776 janelas cada, sem
filtro novo: 606 IDs individuais com janelas, agrupados sob 12 vídeos.
Nenhuma fonte original, pixel de vídeo, validação ou teste foi aberto.

ADE₁₀/FDE₁₀ principais: persistência 3,890964/6,619751 px;
CV 3,137020/5,774373 px. CV tem ADE₁₀ menor em 9/12 vídeos e FDE₁₀ menor em
7/12; a média não descreve melhora uniforme. Agregação: janelas por ID original,
IDs por vídeo e vídeos com pesos iguais. Resultados descritivos de treino com
GT, sem seleção, inferência estatística, fluxo ou avaliação fim a fim.

Conferência independente aprovada na primeira execução: {q['files_verified']} arquivos,
{pt(q['comparisons'],0)} comparações ({pt(q['numeric_comparisons'],0)} numéricas),
{pt(q['elapsed_seconds'],4)} s, previsões e métricas reconstruídas integralmente.
O verificador usa biblioteca padrão e derivados, sem importar o código
científico ou reler fontes. A figura PNG/SVG foi gerada e o PNG revisado.
Os [resultados completos](../metodologia/BASELINES_PREDICAO_V1.md#resultados-da-bateria--08092026)
registram horizontes, pesos secundários, valores por vídeo, hashes e caminhos.

Run: `{RUN.as_posix()}`.
Conferência: `{QA.as_posix()}`.
Próximo: contrato e smoke causal do fluxo aparente local, começando por
Farnebäck. HOTA, preditores aprendidos e confirmação continuam pendentes.
Mapa HTML, guia de navegação e fonte LaTeX atualizados localmente; PDF não
recompilado. A suíte anterior à bateria aprovou 1.362 testes em 144,75 s.
''')

tex = 'monografia/cap_metodo/metodo.tex'
replace(tex,
    'O consumo dos índices, a causalidade das entradas e a avaliação densa de ADE permanecem para a etapa seguinte.',
    'Em etapa posterior, os índices foram consumidos pelos baselines fixos descritos a seguir, com entradas causais e avaliação densa de ADE.')
insert = r'''Como primeira avaliação de predição, persistência e velocidade constante foram fixadas antes dos resultados, sob o commit \texttt{5289c93}. A persistência repete a última posição; a velocidade constante utiliza a mediana componente a componente das cinco últimas diferenças, calculadas a partir de seis posições. Ambos receberam apenas o histórico, em precisão de 64 bits, e produziram todos os passos de 1 a 10 sem limitar as previsões aos contornos da imagem. As 343.776 janelas foram avaliadas por cada método, cobrindo 606 dos 669 IDs individuais originais. Os 63 IDs sem janela permanecem na descrição de cobertura, sem imputação de erro zero. A agregação principal calcula a média de janelas por ID original, reunindo seus segmentos, seguida da média com peso igual entre IDs dentro do vídeo e entre os 12 vídeos. A média por janela dentro de vídeo, seguida de pesos iguais entre vídeos, é secundária.

Na agregação principal, a persistência obteve ADE de 3,890964 pixels e FDE de 6,619751 pixels no horizonte de dez quadros; a velocidade constante obteve 3,137020 e 5,774373 pixels, respectivamente. A redução não foi uniforme: a velocidade constante apresentou ADE menor em nove vídeos e FDE menor em sete. São resultados descritivos nas trajetórias anotadas de treino, condicionados à disponibilidade de futuro de referência, sem ajuste de hiperparâmetros, seleção de método, inferência estatística ou confirmação da hipótese de fluxo. O FPS nominal foi 48 no vídeo 35, 50 no vídeo 82 e 49 nos demais; portanto, dez quadros não correspondem exatamente à mesma duração física em todos os vídeos. Nenhuma reamostragem foi aplicada.

Antes da bateria, 1.362 testes automatizados foram aprovados. A execução completa levou 54,191753 segundos, com RSS amostrado de 199,027 MiB. Uma conferência independente posterior reconstituiu todas as previsões, os erros densos e as agregações a partir dos arquivos exportados e da referência derivada, sem importar a implementação científica ou abrir fontes originais. O manifesto, os arquivos por janela e por ID, a comparação por vídeo e a figura preservam a proveniência da execução. Fluxo, rastreamento e modelos aprendidos não foram avaliados nessa bateria.

'''
replace(tex,'Cada trajetória válida será dividida em histórico de 20 quadros e horizontes de 1, 5 e 10 quadros,',insert+'Cada trajetória válida será dividida em histórico de 20 quadros e horizontes de 1, 5 e 10 quadros,')
replace(tex,
    'A interface atual de avaliação calcula a média dos instantes fornecidos, portanto o produtor de previsões e o avaliador deverão ser conferidos conjuntamente com casos sintéticos antes dos experimentos científicos de predição.',
    'A interface histórica de avaliação calcula a média dos instantes fornecidos e permanece identificada como tal. A bateria fixa de persistência e velocidade constante utilizou uma interface densa própria, verificada com casos sintéticos e por reconstrução independente dos resultados. As futuras variantes deverão satisfazer o mesmo contrato denso e a separação entre histórico e alvos.')

for path, data in pending.items():
    path.write_bytes(data)
print(json.dumps({'updated':[str(p.relative_to(ROOT)) for p in pending], 'run_manifest_sha256':mh,'verification_sha256':qh},ensure_ascii=False))
