"""Record completed level 8a from its authenticated result paths."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[2]
state=json.loads((ROOT/'tmp/flow_scale_v1/result_state.json').read_text(encoding='utf-8'))
run=state['manifest']; qa=state['verification']; mh=state['manifest_sha256']; qh=state['verification_sha256']
source=state['source_hash']; s=state['summary']
def read(p):return (ROOT/p).read_text(encoding='utf-8')
def write(p,t):(ROOT/p).write_text(t,encoding='utf-8',newline='\n')
def replace(p,old,new):
    t=read(p);assert old in t,(p,old);write(p,t.replace(old,new,1))

rows='\n'.join(f"| {r['video_id']} | {r['windows']:,} | {r['unique_samples']:,} | {r['historical_uses']:,} |".replace(',','.') for r in s['videos'])
results=f'''
## Resultado do benchmark — 09/09/2026

**Nível 8a concluído e conferido; extração completa bloqueada pelo orçamento
de tempo.** Código, plano e verificador foram registrados antes dos pixels em
`6110c44526c30f8f8f7a2fdeb276f7169d2fcd88`, após **1.728 testes em 181,93 s**
e self-test independente. A run terminou com Git limpo, reconferido ao final.
O identificador usa UTC em 10/09; a execução ocorreu em 09/09 no fuso de São Paulo.

Os 12 prefixos concluíram 720 quadros, 708 campos forward e 24 backward.
Foram preservadas **10.848 janelas, 15.762 amostras distintas e 206.112 usos
históricos**. Todas as amostras foram numericamente válidas e todas as janelas
tiveram suas cinco amostras finais válidas. Isso não certifica acurácia do fluxo
ou cobertura dos vídeos completos. As 10.848 janelas não são réplicas independentes.

| Vídeo de treino | Janelas | Amostras distintas | Usos históricos |
|---|---:|---:|---:|
{rows}
| **Total** | **10.848** | **15.762** | **206.112** |

O tempo da run foi **199,583442 s**, com **375,145 MiB RSS amostrado** em
734 observações. Foram guardados 193 artefatos e um manifesto: 153.909.176
bytes antes do manifesto final e **154.023.508 bytes finais**. Os 24 pares
sentinelas conservam ambos os sentidos e os 48 quadros cinza correspondentes.
Os parâmetros, o limite de 60 quadros e a coorte não foram alterados.

### Conferência independente

O QA passou na **primeira tentativa**: **288 arquivos**, **934.668 comparações**,
incluindo 127.506 numéricas e 94.572 de coordenadas, em **23,4658582 s**.
Máxima diferença numérica: `3,552713678800501e-15`, abaixo do limite absoluto
de 1e-9, sem tolerância relativa. Foram conferidos 7.372.800 pixels de pares
nos diagnósticos sentinelas e 14.745.600 pixels de campos direcionais retidos.
O QA reconstruiu todas as amostras a partir dos testemunhos e confrontou os
testemunhos sentinelas com os NPZ densos. Não reabriu MP4s ou labels originais,
não importou a implementação científica e não repetiu Farnebäck.
Fora dos sentinelas, os campos descartados continuam não reconstruíveis;
o vínculo dos quatro vizinhos ao estimador depende da procedência do produtor.

- [Manifesto da run](../../{run}); SHA256 `{mh}`.
- [Conferência aprovada](../../{qa}); SHA256 `{qh}`.
- Hash das fontes de código da run: `{source}`.
- [Resumo global](../../{str(Path(run).with_name('summary.json')).replace(chr(92),'/')}) e
  [saídas por vídeo](../../{str(Path(run).parent/'by_video').replace(chr(92),'/')}).
- Figura [PNG](../../data/derived/flow/reports/farneback_compact_benchmark_v1_20260909/benchmark_fluxo_compacto.png),
  [SVG](../../data/derived/flow/reports/farneback_compact_benchmark_v1_20260909/benchmark_fluxo_compacto.svg)
  e [proveniência](../../data/derived/flow/reports/farneback_compact_benchmark_v1_20260909/provenance.json).

### Orçamento e continuidade

A regra registrada projetou **8.052,675671 s (134,21 min)**, acima dos
7.200 s (120 min) permitidos: excesso de 852,675671 s, aproximadamente 11,84%.
Projetou **1.854.533.829,14 bytes (1.768,62 MiB)**, abaixo dos 4.096 MiB.
O estado é `exceeds_planning_budget`; `full_extraction_released=false` e
`full_rss_certified=false`. O próprio benchmark respeitou seus limites;
é a projeção de escala que não passou. Não elevar retroativamente o teto,
retirar o fator de segurança ou omitir parcelas para declarar aprovação.

Com o fator 2 já aplicado, o laço responde por 7.516,522034 s da projeção
(93,34%), as tabelas por 450,794378 s, os sentinelas por 43,485277 s e a
parcela fixa por 41,873983 s. O laço reúne decodificação, estimação,
amostragem e coleta de testemunhos; esses dados não isolam qual subetapa
domina. O próximo marco deverá instrumentar essas parcelas e registrar um
ajuste operacional verificável, se necessário, antes de qualquer novo ensaio.
Eventual paralelismo exige conferir equivalência numérica e recursos, mantendo
os parâmetros científicos, a causalidade e a referência. Isso é continuidade
proposta, não uma otimização já implementada ou um novo benchmark executado.

Após resolver o custo sob plano próprio, registrar a extração completa,
a retenção de índices/memória e a ablação pareada na coorte comum. O preditor
causal está implementado e testado sinteticamente, mas **não foi chamado em
dados reais**. Não há ADE/FDE com fluxo, seleção, promoção ou confirmação da
hipótese. Referência, baselines, smoke e este benchmark permanecem preservados.
'''
p='docs/metodologia/FLUXO_COMPACTO_V1.md'
assert '## Resultado do benchmark' not in read(p);write(p,read(p)+'\n'+results)
entry=f'''## 2026-09-09 — nível 8a conferido: custo ampliado ainda acima do limite

O [benchmark compacto](../metodologia/FLUXO_COMPACTO_V1.md#resultado-do-benchmark--09092026)
terminou em `6110c44`, com Git limpo: 12 treinos, 720 quadros, 708 campos
forward, 24 backward, 10.848 janelas, 15.762 amostras distintas e 206.112 usos.
Todas as amostras e as cinco transições finais de cada janela foram válidas.
Tempo 199,583442 s, RSS amostrado 375,145 MiB e 154.023.508 bytes finais.

Conferência independente aprovada na primeira tentativa: 288 arquivos,
934.668 comparações, 127.506 numéricas, 23,4658582 s, diferença máxima
3,552713678800501e-15. O QA usa derivados e testemunhos; não repete MP4s ou
Farnebäck. A run e seus hashes estão no protocolo, assim como o limite da
conferência dos campos não retidos. O identificador UTC é de 10/09; a data
local da execução é 09/09, em São Paulo.

A projeção registrada excedeu o limite de tempo: 8.052,675671 s contra
7.200 s; os 1.768,62 MiB projetados cabem no limite de 4.096 MiB. A extração
completa permanece bloqueada. O laço de decodificação/estimação/amostragem
responde por 93,34% da projeção; a próxima etapa deverá medir suas parcelas
e registrar um ajuste operacional verificável. O teto original foi preservado.

Este marco não executou preditores em dados reais nem avaliou a hipótese.
Figura, relatório, atlas, guia e método da monografia foram atualizados
localmente; HTMLs e orientações locais seguem fora dos commits. Não repetir
as baterias encerradas nem ampliar a extração por esta CLI.

'''
p='docs/projeto/DIARIO.md';replace(p,'## 2026-09-09 — nível 8a: protocolo compacto',entry+'## 2026-09-09 — nível 8a: protocolo compacto')
replace('docs/projeto/MATRIZ_EXPERIMENTOS.md','| Nível 8a registrado antes dos pixels | Benchmark compacto de custo/integridade nos 12 treinos, prefixos 0..59; CV com fluxo causal testada sinteticamente. Predição real e extração completa ainda pendentes |','| Nível 8a concluído e conferido | 720 quadros, 10.848 janelas, 15.762 amostras distintas; QA 288 arquivos. Projeção 134,21 min acima do teto 120 min; extração completa bloqueada. Preditor com fluxo só testado sinteticamente |')
replace('README.md','O próximo marco mede custo e integridade da extração\n   compacta, antes da ablação pareada com e sem fluxo.','O benchmark compacto também terminou nos 12 treinos, com QA\n   aprovado. Sua projeção de 134,21 min excedeu o teto de 120 min; a próxima\n   etapa deve medir e ajustar o custo operacional antes da extração completa\n   e da ablação pareada com e sem fluxo.')
p='docs/algoritmos/fluxo/farneback.md';replace(p,'[Índice da família]', '''O [benchmark compacto do nível 8a](../../metodologia/FLUXO_COMPACTO_V1.md)
foi concluído em `6110c44` e conferido independentemente: 720 quadros dos
12 treinos, 10.848 janelas e 15.762 amostras distintas válidas. Sua projeção
de tempo (134,21 min) ultrapassa o teto de 120 min; a extração completa
permanece bloqueada. O próximo ajuste deve medir as parcelas do laço e
preservar os parâmetros científicos. Isso não avalia o preditor ou a hipótese.

[Índice da família]''')
print('Documentação pública atualizada a partir do benchmark conferido.')
