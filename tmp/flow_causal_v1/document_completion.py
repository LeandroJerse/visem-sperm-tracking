from pathlib import Path
from datetime import datetime, timezone
from hashlib import sha256
import json

ROOT = Path(__file__).resolve().parents[2]
BASE = 'data/tests/flow/farneback/farneback_causal_smoke_v1__cfg0609f968/smoke/'
RUN = BASE + '20260909T203917667291Z__16eecbb__cfgf7e0afa345b3__src3f9307153a__s42/'
FIG = 'data/derived/flow/reports/farneback_causal_smoke_v1_20260909/'
def read(p): return (ROOT/p).read_text(encoding='utf-8')
def write(p,s): (ROOT/p).write_text(s, encoding='utf-8', newline='\n')
def replace(p,old,new):
    s=read(p); assert old in s, (p,old[:80]); write(p,s.replace(old,new,1))

assert sha256((ROOT/RUN/'manifest.json').read_bytes()).hexdigest() == 'fff845df9b10c743b227e0f459b502218677840d021c6190736041507b7f1d98'
assert sha256((ROOT/BASE/'verification_20260909_retry1.json').read_bytes()).hexdigest() == 'b44db2e80e727afe067ee5ba6b95b97d7c2a9c32491fec045bf54ec9fa7c6652'

results = f'''
## Resultados do smoke — 09/09/2026

Protocolo, código e execução registrados em
`16eecbb32b3edb4b4908ced344367670132a4cc1`, com Git limpo e reconferido.
A suíte completa selecionada (`not optional_ml and not slow`) aprovou
**1.495 testes em 160,71 s** antes dos pixels. O verificador passou também
em 12 grupos sintéticos. Este registro posterior preserva o desenho acima.

A execução terminou em **56,923953 s**, com RSS máximo amostrado de
**289,598 MiB** (196 amostras), 193.923.149 bytes antes do manifesto e
**193.999.043 bytes finais**. Foram produzidos 97 artefatos mais o manifesto.
Os 40 quadros são o prefixo 0..19 dos dois vídeos, em 640×480 e FPS nominal49;
não se avaliou a completude dos 1.470 quadros de cada vídeo.

| Vídeo de treino | Janelas na origem19 | Amostras históricas | Válidas / inválidas | Pares / campos / trios |
|---|---:|---:|---:|---:|
| 11 | 42 | 798 | 798 / 0 | 19 / 38 / 18 |
| 12 | 26 | 494 | 494 / 0 | 19 / 38 / 18 |
| Total | 68 | 1.292 | 1.292 / 0 | 38 / 76 / 36 |

Todas as janelas escolhidas antes dos pixels foram preservadas. Validade de
100% nesta amostra significa suporte numérico finito, não acurácia de 100%.
A elegibilidade continua condicionada ao futuro completo da referência; o
consumidor recebeu apenas as 20 posições históricas, sem coordenadas futuras.

| Vídeo | MAE fotométrica zero | MAE fotométrica após warp | Consistência FB média (px) | Mudança temporal média (px) |
|---|---:|---:|---:|---:|
| 11 | 0,003008 | 0,002374 | 0,015067 | 0,131004 |
| 12 | 0,005554 | 0,003461 | 0,169551 | 0,571267 |

A fotometria usa intensidade cinza/255 e suporte idêntico entre zero e warp
em cada par. Cada vídeo dá peso igual aos 19 pares com suporte. O suporte
fotométrico/FB médio foi 0,996679 no vídeo11 e 0,996328 no12; as frações FB
≤1,5px foram 0,999370 e 0,983397. A mudança temporal dá peso igual aos 18
trios com suporte. Seus p95 médios foram 0,548537 e 3,611518px, com suporte
médio 0,996658 e 0,996319, respectivamente. Valores completos e denominadores
permanecem nos CSVs. Menor erro fotométrico nos dois prefixos é um diagnóstico
descritivo; mudança temporal maior pode incluir mudança real do movimento.

Os tempos de estimação forward/backward somaram 5,893733s no vídeo11 e
5,888907s no12; diagnósticos, 8,951774s e 8,914980s. O tempo total inclui
verificações, decodificação, exportação e demais operações. Esses valores
não são latência de predição nem custo da pipeline fim a fim.

### Conferência independente e falha preservada

A primeira tentativa parou no esquema da referência histórica, com zero
comparações numéricas. Seu relatório foi preservado. O commit
`0fccda8f663dc64a9ebc815b8cbaa60d5146fde1` corrigiu exclusivamente a leitura
do esquema de cinco campos do QA pai, verificando também `mtime_ns` e
`expected_hash_verified`. Nove regressões sintéticas passaram em 4,32s.
Não se alteraram a run, o plano, a tolerância ou o estimador; Farnebäck não
foi repetido. Essa correção não substitui `16eecbb` na proveniência da run.

A segunda conferência passou em **21,051553s**: **190 arquivos**, **37.406
comparações**, das quais **8.378 numéricas**, incluindo 5.304 coordenadas
comparadas exatamente. Reconstituiu as 68 janelas, 1.292 amostras e todos os
resumos. A maior diferença foi **8,881784197001252e-16**, abaixo do limite
absoluto registrado de 1e-9. Foram diagnosticadas 11.673.600 posições de
pixels por par e 11.059.200 posições temporais; essas contagens vetorizadas
são distintas das comparações escalares. Os campos dos dois sentidos
totalizam 23.347.200 posições verificadas quanto a formato/validade.

A conferência recalculou amostragem e diagnósticos com SciPy, sem importar
o código científico, reler MP4/labels ou executar o estimador. Ela autentica
os derivados e sua matemática; não constitui decodificação independente do
MP4 nem prova independente de que cada campo seja a saída do Farnebäck.
Esses vínculos dependem do produtor registrado e de seus testes sintéticos.

- [Manifesto da run](../../{RUN}manifest.json), SHA-256
  `fff845df9b10c743b227e0f459b502218677840d021c6190736041507b7f1d98`.
- Código fonte da execução: SHA-256
  `3f9307153a3c7c661ba59b007e8d003b5cecdc6b93bec18f5cb32d12c243879b`.
- [Resumo e saídas por vídeo](../../{RUN}summary.json).
- [Primeira conferência preservada](../../{BASE}verification_20260909.json).
- [Conferência aprovada](../../{BASE}verification_20260909_retry1.json), SHA-256
  `b44db2e80e727afe067ee5ba6b95b97d7c2a9c32491fec045bf54ec9fa7c6652`.
- [Figura PNG](../../{FIG}smoke_fluxo_causal.png) e
  [SVG](../../{FIG}smoke_fluxo_causal.svg), derivados da run conferida.
  Setas do par18→19 ampliadas em 5× para leitura, sem interpretação física.

**Nível7 concluído e conferido.** Há evidência de funcionamento da conexão
causal imagem–histórico nesta amostra. Não há seleção de Farnebäck, teste de
ganho em ADE/FDE, confirmação estatística ou avaliação de rastreamento.
Validação/teste originais e runs anteriores não foram reabertos.
O próximo marco é registrar o estudo de características em amostra maior do
treino e a ablação pareada: mesmas janelas e alvos, normalização ajustada no
treino correspondente, tratamento explícito das ausências, modelos e orçamento
comparáveis e agregação por ID/vídeo. Esse contrato ainda será detalhado antes
de novas extrações; não há autorização metodológica implícita para varrer
parâmetros com base nos diagnósticos deste smoke.
'''
p='docs/metodologia/FLUXO_CAUSAL_V1.md';write(p,read(p)+results)

entry=f'''## 2026-09-09 — nível 7 concluído: fluxo causal conferido no treino

O [smoke causal de Farnebäck](../metodologia/FLUXO_CAUSAL_V1.md#resultados-do-smoke--09092026)
terminou em `16eecbb`, com Git limpo: 40 quadros dos treinos11/12, 38 pares,
76 campos e 36 diagnósticos temporais. Todas as 68 janelas selecionadas na
origem19 foram preservadas, com 1.292 amostras numericamente válidas e zero
inválidas. Vinte posições fornecem 19 transições; o último par é18→19 e a
amostragem ocorre no centro do primeiro quadro do par, sem coordenadas futuras.

Tempo total56,923953s, RSS amostrado289,598MiB, 193.999.043 bytes finais.
Nos vídeos11/12, as MAEs fotométricas após warp foram0,002374/0,003461,
contra0,003008/0,005554 com deslocamento zero nos mesmos suportes.
São diagnósticos dos prefixos, sem inferência, seleção ou teste de predição.

A primeira conferência falhou apenas na leitura do esquema histórico; a
correção em `0fccda8` passou em nove testes, preservando a tentativa e a run.
A segunda conferência passou: 190 arquivos, 37.406 comparações (8.378
numéricas), 21,051553s e diferença máxima8,881784197001252e-16.
O verificador recompôs a matemática dos derivados, sem reler fontes ou
repetir Farnebäck. O protocolo registra seus limites e os hashes exatos.

Run: `{RUN}manifest.json`.
QA: `{BASE}verification_20260909_retry1.json`.
Figura, relatório didático, atlas, guia e método da monografia foram atualizados
localmente. HTMLs, orientações locais e monografia permanecem fora dos commits.
O PDF não foi recompilado. A referência individual e os baselines estão
preservados. Próximo marco: detalhar protocolo da extração causal ampliada e
da ablação pareada com/sem fluxo; hipótese, tracking/HOTA e confirmação seguem
pendentes. Não repetir esta execução encerrada.

'''
replace('docs/projeto/DIARIO.md','## 2026-09-09 — compatibilidade',entry+'## 2026-09-09 — compatibilidade')
replace('docs/projeto/MATRIZ_EXPERIMENTOS.md','| Nível 7 em preparação | Contrato prospectivo e executor estrito do smoke causal de Farnebäck; testes anteriores aos pixels, sem busca ou predição |','| Nível 7 concluído e conferido | Farnebäck causal em 11/12, origem19: 40 quadros, 68 janelas, 1.292 amostras válidas; QA190 arquivos. Sem busca, ablação ou predição |')
replace('docs/projeto/MATRIZ_EXPERIMENTOS.md','O contrato de máscara une boxes', '**Atualização de 09/09/2026:** [smoke causal de Farnebäck](../metodologia/FLUXO_CAUSAL_V1.md) concluído e conferido em `16eecbb`, QA corrigido em `0fccda8`. Uma configuração fixa, sem máscara, quadros0..19 dos treinos11/12. A coluna busca/val real permanece pendente: este smoke não seleciona parâmetros nem testa a hipótese.\n\nO contrato legado de máscara une boxes')
replace('docs/algoritmos/fluxo/farneback.md','Sua execução e conferência serão registradas após os testes. O espaço de busca\nlegado não foi executado nesta etapa.','Execução em `16eecbb` concluída e conferida: 40 quadros, 68 janelas e 1.292\namostras históricas válidas. O QA aprovado após a correção de esquema em\n`0fccda8` conferiu190 arquivos, sem repetir o estimador. Consulte resultados,\ncustos, limites e hashes no contrato. O espaço de busca legado não foi\nexecutado nesta etapa; a hipótese de ganho na predição continua pendente.')
replace('docs/algoritmos/fluxo/farneback.md','## Parâmetros a testar','## Espaço legado previsto — ainda não executado')
replace('docs/algoritmos/fluxo/farneback.md','híbrido, mas seu resultado puro será preservado para comparação. Promover pela\ncombinação de erro fotométrico, consistência e latência. Resultado: **pendente**.','híbrido, mas seu resultado puro será preservado para comparação. O smoke\ncausal está concluído; busca, ablação e avaliação científica ampliada seguem\n**pendentes**, sob plano próprio. Fotometria, consistência e custo são\ndiagnósticos complementares; não usar um placar subjetivo ou interpretá-los\ncomo prova de ganho em ADE/FDE.')

guide=f'''Registro atual: **nível 7 concluído e conferido — 09/09/2026**.
Protocolo/código/run em `16eecbb32b3edb4b4908ced344367670132a4cc1`, com Git
limpo. Suite selecionada:1.495 testes/160,71s antes dos pixels. Smoke11/12,
quadros0..19:40 quadros,38 pares,76 campos,68 janelas,1.292 amostras válidas,
zero inválidas;56,923953s,289,598MiB RSS amostrado,193.999.043 bytes finais.
Conferência:190 arquivos,37.406 comparações (8.378 numéricas),21,051553s;
máxima diferença8,881784197001252e-16. A primeira falha de esquema do
verificador foi preservada; correção em `0fccda8`, com nove testes sintéticos,
sem alterar ou repetir a run. Consulte a seção16 para todas as entradas.
Não há teste da hipótese ou promoção. O próximo marco é registrar protocolo
da extração causal ampliada e ablação equivalente com/sem fluxo no treino.
Preservar referência, baselines e smoke; não repetir baterias encerradas.

'''
section=f'''
## 16. Fluxo causal — nível 7 concluído e conferido

Leia primeiro o [contrato e resultados](../metodologia/FLUXO_CAUSAL_V1.md).
O [plano fixo](../../configs/flow/farneback/causal_smoke_v1.yaml) foi registrado
antes dos pixels. Em t19 só existem os pares0→1..18→19. Cada vetor é amostrado
em p_s, com interpolação estrita em float64, não em p_(s+1). Ausência não é
zero; validade numérica não é acurácia. Os campos são movimento aparente.

| Tarefa | Caminho |
|---|---|
| Consumidor causal, índices, NPZ, validade, interpolação e diagnósticos | [src/flow/causal.py](../../src/flow/causal.py) |
| Históricos sem coordenadas futuras | [src/prediction/reference.py](../../src/prediction/reference.py), `history_batch_at_origin` |
| Orquestração estrita e recursos | [src/experiments/causal_flow_smoke.py](../../src/experiments/causal_flow_smoke.py) |
| CLI oficial e conferência independente | [causal_smoke.py](../../script/flow/test/causal_smoke.py) e [verify_causal_smoke.py](../../script/flow/test/verify_causal_smoke.py); comandos em [script/README.md](../../script/README.md) |
| Testes sintéticos | [núcleo](../../tests/integration/test_causal_flow.py), [executor](../../tests/experiments/test_causal_flow_smoke.py), [verificador](../../tests/experiments/test_causal_flow_verification.py) |
| Run completa e resumo | [manifest.json](../../{RUN}manifest.json), [summary.json](../../{RUN}summary.json), [by_video](../../{RUN}by_video) |
| Tentativa falha preservada / conferência aprovada | [primeira](../../{BASE}verification_20260909.json) / [segunda](../../{BASE}verification_20260909_retry1.json) |
| Figura e proveniência | [PNG](../../{FIG}smoke_fluxo_causal.png), [SVG](../../{FIG}smoke_fluxo_causal.svg), [provenance.json](../../{FIG}provenance.json) |

Manifesto SHA256:`fff845df9b10c743b227e0f459b502218677840d021c6190736041507b7f1d98`.
QA SHA256:`b44db2e80e727afe067ee5ba6b95b97d7c2a9c32491fec045bf54ec9fa7c6652`.
Fontes do código da run:`3f9307153a3c7c661ba59b007e8d003b5cecdc6b93bec18f5cb32d12c243879b`.
Plano canônico:`f7e0afa345b3774127bb622a03ab21d1100dd9655dbd7bb0c6c3eaaa4f13708f`.

`frames/*.npy` guarda os cinzas observados; `pairs/*.npz` os dois sentidos e
validade; índices ligam conteúdo, vídeo, par e configuração por hash.
`selected_windows.csv` e `histories.csv` preservam a referência histórica;
`features.csv` traz19 vetores por janela; `window_coverage.csv` guarda
ausências; `pair_metrics.csv` e `temporal_metrics.csv` guardam denominadores e
diagnósticos. Não confundir68 janelas com68 réplicas independentes: são2 vídeos.
O QA reconstrói a matemática dos derivados; não refaz decodificação/estimação.

O próximo contrato deverá fixar amostra e orçamento ampliados, política para
ausências e coorte comum, preditores equivalentes, ajuste/normalização no treino
correspondente, horizontes e agregação por ID/vídeo. Não selecionar amostras por
erro futuro. Registrar os critérios antes de novas extrações. Máscaras/anéis,
tracking/HOTA, RAFT e ablação aprendida continuam exigindo desenho próprio.
'''
p='docs/projeto/NAVEGACAO.md'
s=read(p).replace('Atualizado em 2026-09-08.', 'Atualizado em 2026-09-09.',1).replace('de 08/09/2026.', 'atualizado em 09/09/2026.',1)
s=s.replace('O nível 6 permanece concluído e o contrato causal de Farnebäck\ncontinua sendo o próximo passo.', 'O nível7 está concluído e conferido. O próximo marco é o protocolo da\nextração causal ampliada e da ablação com/sem fluxo.')
s=s.replace('Registro atual: **nível 6 concluído e conferido**.',guide+'Marco anterior: **nível 6 concluído e conferido**.',1)
s=s.replace('Foram conferidos 854 links locais do relatório,', 'Na edição de08/09 foram conferidos854 links locais do relatório,',1)
write(p,s+section)

p='AGENTS.md';s=read(p);s=s.replace('Síntese didática completa de 08/09/2026 em','Síntese didática completa atualizada em 09/09/2026 em',1)
s=s.replace('A preparação do relatório foi documental, sem novas runs: o próximo marco\npermanece o contrato causal de Farnebäck.', 'A atualização do relatório usa derivados já conferidos. O smoke causal do\nnível7 foi executado separadamente; o próximo marco é registrar extração\ncausal ampliada e ablação pareada com/sem fluxo.')
s=s.replace('Marco atual de 08/09/2026:',guide+f'Run do nível7: `{RUN}manifest.json`.\nQA: `{BASE}verification_20260909_retry1.json`.\nManifesto SHA256:`fff845df9b10c743b227e0f459b502218677840d021c6190736041507b7f1d98`.\nQA SHA256:`b44db2e80e727afe067ee5ba6b95b97d7c2a9c32491fec045bf54ec9fa7c6652`.\nO novo consumidor causal e os hashes substituem o caminho legado somente\npara esta nova cadeia. `future_flow_mode=observed` continua proibido.\nA conferência não decodifica MP4 nem refaz Farnebäck; essa limitação permanece\nexplícita. Seção16 do guia e bloco `fluxo-causal-nivel7` do atlas.\n\nMarco anterior de 08/09/2026:',1)
s=s.replace('o marco\natual é o nível 5 descrito no início.', 'o marco\natual é o nível7 descrito no início.')
write(p,s)

latex=r'''
Como verificação inicial da conexão causal com a referência individual, foi
registrado e executado um ensaio de Farnebäck sob o commit \texttt{16eecbb},
após 1.495 testes automatizados. Foram utilizados somente os quadros de 0 a 19
dos vídeos de treino 11 e 12, sem máscara ou busca de parâmetros. Na origem
$t=19$, cada um dos 19 campos históricos $F_s$, que representa $s\to s+1$,
foi amostrado no centro anotado $\mathbf p_s$ do primeiro quadro do par, com
interpolação bilinear e pesos em precisão de 64 bits. O último par disponível
é $18\to19$; nenhuma imagem posterior foi fornecida ao estimador. O consumidor
recebeu apenas o histórico e as chaves das janelas, sem coordenadas futuras.
A elegibilidade continua condicionada à disponibilidade de futuro completo
na referência derivada, exclusivamente para avaliação retrospectiva.

As 68 janelas selecionadas antes dos pixels produziram 1.292 amostras com
suporte numérico válido, sem exclusões. Os 38 pares foram estimados nos dois
sentidos, totalizando 76 campos, além de 36 comparações temporais. Os erros
fotométricos médios após alinhamento foram 0,002374 e 0,003461 nos vídeos 11
e 12, contra 0,003008 e 0,005554 com deslocamento zero, em intensidade cinza
dividida por 255 e sobre o mesmo suporte de cada par. As consistências
direto--reverso médias foram 0,015067 e 0,169551 pixels. As médias por vídeo
dão peso igual aos pares com suporte. Validade numérica de todas as amostras
não implica acurácia de 100\%, e esses diagnósticos não medem a velocidade
física do fluido nem o ganho em predição.

O ensaio levou 56,923953 segundos, com RSS máximo amostrado de 289,598 MiB.
A conferência independente verificou 190 arquivos e 37.406 comparações,
das quais 8.378 numéricas, com diferença máxima de $8{,}88\times10^{-16}$,
abaixo da tolerância absoluta de $10^{-9}$. Uma falha inicial na leitura do
esquema do relatório histórico da referência foi preservada e corrigida sob
\texttt{0fccda8}, após nove testes sintéticos, sem modificar ou repetir a run.
A conferência reconstituiu a matemática dos derivados, sem importar a
implementação científica; não constitui decodificação independente do MP4 ou
reexecução do estimador. O ensaio certifica a conexão operacional nesse
prefixo de dois vídeos. A extração ampliada e a ablação pareada com e sem fluxo
permanecem sujeitas a contrato prospectivo próprio.

'''
replace('monografia/cap_metodo/metodo.tex','\\section{Predição das trajetórias}',latex+'\\section{Predição das trajetórias}')
replace('monografia/cap_metodo/metodo.tex','As trajetórias serão filtradas, normalizadas e convertidas em pares de janelas observadas e futuras.', 'As trajetórias serão segmentadas por continuidade e elegibilidade documentadas, preservando as exclusões. Janelas observadas e futuras serão separadas; normalizações dos preditores serão ajustadas somente no treino correspondente, sem filtrar trajetórias por velocidade ou erro futuro.')
replace('monografia/README.md','## Versão de trabalho — 08/09/2026','## Versão de trabalho — 09/09/2026')
replace('monografia/README.md','A fonte corrigida ainda não foi recompilada.', 'Em09/09, o método passou a registrar o smoke causal de Farnebäck em11/12:\n40 quadros,68 janelas,1.292 amostras e conferência independente aprovada.\nEsse ensaio verifica a conexão causal e os diagnósticos; a ablação continua\npendente. O contrato e os resultados estão em `docs/metodologia/FLUXO_CAUSAL_V1.md`.\n\nA fonte corrigida ainda não foi recompilada.')
print('Public results and local navigation/monograph updated; no scientific artifacts changed.')
