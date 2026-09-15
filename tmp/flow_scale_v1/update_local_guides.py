from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[2]
state=json.loads((ROOT/'tmp/flow_scale_v1/result_state.json').read_text(encoding='utf-8'))
run=state['manifest'];qa=state['verification']
def read(p):return (ROOT/p).read_text(encoding='utf-8')
def write(p,t):(ROOT/p).write_text(t,encoding='utf-8',newline='\n')
current=f'''Registro atual: **nível 8a concluído e conferido — 09/09/2026**.
O benchmark compacto de engenharia terminou em `6110c44526c30f8f8f7a2fdeb276f7169d2fcd88`,
com Git limpo, após 1.728 testes em 181,93 s. Foram 720 quadros nos 12 treinos,
708 campos forward, 24 backward, 10.848 janelas, 15.762 amostras distintas
válidas e 206.112 usos. Todas as janelas têm as cinco amostras finais válidas.
Tempo 199,583442 s, RSS amostrado 375,145 MiB, 154.023.508 bytes finais.
QA aprovado na primeira tentativa: 288 arquivos, 934.668 comparações,
127.506 numéricas, 94.572 coordenadas, 23,4658582 s; diferença máxima
3,552713678800501e-15. O QA usa os testemunhos de todas as amostras e os
campos densos sentinelas, sem decodificar fontes ou refazer Farnebäck.

**A projeção de tempo NÃO passou:** 8.052,675671 s (134,21 min) >7.200 s
(120 min). Os 1.768,62 MiB projetados cabem nos 4.096 MiB; RAM completa
continua não certificada. Não elevar o teto retroativamente, remover fator2
ou executar a extração completa com esta CLI. O laço responde por 93,34% do
tempo projetado, mas reúne decodificação/estimação/amostragem/testemunhos.
Próximo marco: registrar instrumentação dessas parcelas e ajuste operacional
verificável, com equivalência numérica e recursos, antes de novo ensaio.
Depois, plano completo de extração, memória/índices e ablação pareada.
Não repetir as baterias encerradas. Não há ADE/FDE com fluxo, seleção,
promoção ou teste da hipótese. O preditor causal existe e só foi testado
sinteticamente. `future_flow_mode=observed` segue proibido.

Run: `{run}`.
QA: `{qa}`.
Manifesto SHA256: `{state['manifest_sha256']}`.
QA SHA256: `{state['verification_sha256']}`.
Código-fonte SHA256: `{state['source_hash']}`.
Plano e contrato: `configs/flow/farneback/compact_benchmark_v1.yaml` e
`docs/metodologia/FLUXO_COMPACTO_V1.md`. Entradas e arquivos na seção 17 do
guia; bloco `fluxo-compacto-nivel8a` no atlas. O identificador da run é UTC
de 10/09; a data local da execução é 09/09 em São Paulo. HTMLs, guias e
monografia permanecem fora dos commits. Preservar fontes e runs anteriores.

'''
p='AGENTS.md';t=read(p);assert 'Registro atual: **nível 8a' not in t
t=t.replace('O smoke causal do\nnível 7 foi executado separadamente; o próximo marco é registrar extração\ncausal ampliada e ablação pareada com/sem fluxo.','O benchmark compacto do\nnível 8a foi executado separadamente; sua projeção excedeu o teto de tempo.\nO próximo marco é medir e ajustar o custo antes da extração ampliada e ablação.')
t=t.replace('Registro atual: **nível 7 concluído e conferido — 09/09/2026**.',current+'Marco anterior: **nível 7 concluído e conferido — 09/09/2026**.',1);write(p,t)
p='docs/projeto/NAVEGACAO.md';t=read(p)
t=t.replace('O nível 7 está concluído e conferido. O próximo marco é o protocolo da\nextração causal ampliada e da ablação com/sem fluxo.','O nível 8a está concluído e conferido, mas sua projeção de tempo excedeu o\nlimite. O próximo marco deve medir e ajustar o custo antes da extração completa\ne da ablação com/sem fluxo.')
t=t.replace('A atualização de 09/09 tem quatro figuras incorporadas','A atualização histórica do nível 7, em 09/09, tem quatro figuras incorporadas')
t=t.replace('Registro atual: **nível 7 concluído e conferido — 09/09/2026**.',current+'Marco anterior: **nível 7 concluído e conferido — 09/09/2026**.',1)
section=f'''
## 17. Fluxo compacto — nível 8a conferido, custo ampliado bloqueado

Comece pelo [contrato e resultado](../metodologia/FLUXO_COMPACTO_V1.md).
Este marco é benchmark de engenharia; não é a ablação do nível 8 inteiro.
O limite prospectivo de tempo ampliado foi excedido e permanece preservado.

| Procurar | Arquivo |
|---|---|
| Plano imutável: 12 treinos, prefixos 0..59, limites, coorte e projeção | [compact_benchmark_v1.yaml](../../configs/flow/farneback/compact_benchmark_v1.yaml) |
| Construção histórica sem retorno dos alvos | [reference.py](../../src/prediction/reference.py), `VideoReference.iter_history_batches` |
| Deduplicação, ligações, validade, cobertura e quatro vizinhos | [compact.py](../../src/flow/compact.py) |
| Produtor sequencial, retenção sentinela, recursos e projeção | [compact_flow_benchmark.py](../../src/experiments/compact_flow_benchmark.py) |
| Preditor causal float64 com cinco fluxos finais | [causal_constant_velocity.py](../../src/prediction/hybrid/causal_constant_velocity.py); somente testes sintéticos até aqui |
| CLI e conferência independente | [compact_benchmark.py](../../script/flow/test/compact_benchmark.py), [verify_compact_benchmark.py](../../script/flow/test/verify_compact_benchmark.py); comandos em [script/README.md](../../script/README.md) |
| Testes | [compactação](../../tests/integration/test_compact_flow.py), [preditor](../../tests/integration/test_causal_flow_prediction.py), [executor](../../tests/experiments/test_compact_flow_benchmark.py), [conferência](../../tests/experiments/test_compact_flow_verification.py) |
| Run e saídas | [manifesto](../../{run}), [summary](../../{str(Path(run).with_name('summary.json')).replace(chr(92),'/')}), [by_video](../../{str(Path(run).parent/'by_video').replace(chr(92),'/')}) |
| QA aprovado na primeira tentativa | [verification_20260909.json](../../{qa}) |
| Figura | [PNG](../../data/derived/flow/reports/farneback_compact_benchmark_v1_20260909/benchmark_fluxo_compacto.png), [SVG](../../data/derived/flow/reports/farneback_compact_benchmark_v1_20260909/benchmark_fluxo_compacto.svg), [proveniência](../../data/derived/flow/reports/farneback_compact_benchmark_v1_20260909/provenance.json) |

`selected_windows.csv` guarda as janelas e chaves originais; `requests.csv`
as amostras distintas; `links.csv` liga cada janela a seus 19 identificadores.
`features.csv` guarda u/v, validade e motivo; `window_coverage.csv` guarda
contagens das 19 transições e das cinco usadas pelo preditor. `witnesses.npz`
preserva os quatro vizinhos de cada interpolação. `frame_index.json` e
`pair_index.json` ligam hashes e fontes; `frames/` e `checkpoints/` retêm
somente os sentinelas 0→1 e 58→59. `checkpoint_metrics.csv` descreve apenas
esses pares; não representa todos os 59 pares de cada prefixo.

Fora dos sentinelas, o hash não recompõe o campo descartado: o QA confere a
interpolação dos testemunhos e a procedência registrada, sem repetir o
estimador. Vetor numericamente válido não significa movimento verdadeiro.
O benchmark respeitou seus próprios tetos, mas a projeção ficou em 134,21 min
contra 120 min; não está liberada a extração completa. Próximo trabalho:
instrumentar o laço dominante, registrar ajuste e equivalência antes de novo
ensaio; depois registrar extração e ablação completas. Não mudar parâmetros
para melhorar o erro, não elevar orçamento retroativamente e não repetir
referência, baselines, smoke ou esta run encerrada.
'''
assert '## 17. Fluxo compacto' not in t;write(p,t+'\n'+section)
p='monografia/cap_metodo/metodo.tex';t=read(p)
paragraph=r'''
Para preparar a escala, foi registrado antes dos pixels um benchmark de
armazenamento compacto sob o commit \texttt{6110c44}, após 1.728 testes.
Foram processados os quadros de 0 a 59 de cada um dos 12 vídeos de treino,
com a mesma configuração de Farnebäck, uma thread de CPU e OpenCL desativado.
Os 708 campos diretos foram amostrados nas posições históricas de origem.
Foram retidos campos densos nos dois sentidos apenas nos pares $0\to1$ e
$58\to59$ de cada vídeo, além de seus quadros cinza. As 10.848 janelas
compartilham 15.762 amostras distintas, correspondentes a 206.112 usos.
Cada amostra preserva os quatro vizinhos usados na interpolação; o QA pode
reconstruir seus pesos e valores, mas somente nos sentinelas pode confrontar
os vizinhos com o campo denso retido. Não houve segunda decodificação ou
reexecução independente do estimador. Todas as amostras tiveram suporte
numérico válido, sem que isso certifique acurácia do movimento estimado.

O benchmark terminou em 199,583442 segundos, com RSS amostrado de 375,145 MiB
e 154.023.508 bytes finais. A conferência independente passou na primeira
tentativa: 288 arquivos e 934.668 comparações, com diferença máxima de
$3{,}55\times10^{-15}$. A regra de projeção, fixada antes dos resultados e
com fator de segurança dois, estimou 8.052,675671 segundos e 1.768,62 MiB para
a escala completa. O tempo excedeu o teto prospectivo de 7.200 segundos;
o armazenamento permaneceu abaixo dos 4.096 MiB. Por isso, a extração completa
não foi liberada. A próxima etapa deverá discriminar os custos de decodificação,
estimação e amostragem e registrar eventual ajuste operacional com conferência
de equivalência, mantendo o orçamento original. Não houve avaliação de ADE/FDE
com fluxo, seleção de parâmetros ou teste da hipótese neste benchmark.

'''
assert paragraph not in t;t=t.replace(r'\section{Predição das trajetórias}',paragraph+r'\section{Predição das trajetórias}',1)
pred=r'''
Foi também implementada uma variante causal fixa da velocidade constante,
em precisão de 64 bits. Para as cinco últimas transições observadas, define-se
$\mathbf g_s=F_s(\mathbf p_s)$ e utiliza-se
\begin{equation}
\widehat{\mathbf p}_{t+h}=\mathbf p_t+h\left[
\mathop{\mathrm{mediana}}_{s=t-5}^{t-1}
(\mathbf p_{s+1}-\mathbf p_s-\mathbf g_s)+\mathbf g_{t-1}\right],
\quad h=1,\ldots,10.
\end{equation}
A mediana é calculada por componente. O resíduo é algébrico, sem interpretação
de velocidade intrínseca ou física do fluido. Se o fluxo histórico é constante,
sua subtração e reposição reproduzem o baseline de velocidade constante dentro
da tolerância numérica; esse controle e as recusas de entradas futuras foram
verificados sinteticamente. A avaliação real permanece pendente. Os dois braços
deverão usar a mesma coorte com as cinco amostras finais válidas, reportando
também a cobertura das 19 transições. Ausências anteriores que não entram na
fórmula não excluem por si mesmas a janela, e ausência válida não é imputada
como vetor zero.

'''
pred=pred.replace('ausência válida não é imputada','ausência de fluxo não é imputada')
t=t.replace(r'\section{Critérios de validação e comparação}',pred+r'\section{Critérios de validação e comparação}',1);write(p,t)
print('AGENTS, guia permanente e fonte LaTeX local atualizados.')
