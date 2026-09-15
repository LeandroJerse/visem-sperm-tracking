import json
from pathlib import Path
from src.core.artifacts import sha256_file

ROOT=Path(__file__).resolve().parents[1]
parent=Path('data/derived/prediction/ground_truth_individuals/individual_trajectories_v1__cfgc9793dcb/preparation')
batch=parent/'20260908T193624353498Z__33d191d__cfgf6cda613a4fe__srcca22c3a977__s42'
qa_path=parent/'verification_20260908.json'
figure=Path('data/derived/prediction/reference_reports/individual_trajectories_v1_20260908')
m=json.loads((ROOT/batch/'manifest.json').read_text())
q=json.loads((ROOT/qa_path).read_text())
assert m['status']=='complete' and q['status']=='passed' and m['git_dirty'] is False
assert sha256_file(ROOT/batch/'manifest.json')==q['run_manifest_sha256']
assert q['totals_rebuilt']==m['summary']['totals']
assert json.loads((ROOT/figure/'visual_review.json').read_text())['status']=='passed'
def fmt(value):return f'{value:,}'.replace(',','.')
def append(name,text):
    with (ROOT/name).open('a',encoding='utf-8',newline='\n') as out:out.write('\n'+text+'\n')
def replace(name,old,new):
    p=ROOT/name;data=p.read_bytes()
    # Preserve existing mixed newline sequences outside the exact edited range.
    old_b=old.encode();new_b=new.encode()
    if data.count(old_b)!=1:
        old_b=old.replace('\n','\r\n').encode();new_b=new.replace('\n','\r\n').encode()
    assert data.count(old_b)==1,(name,data.count(old_b))
    p.write_bytes(data.replace(old_b,new_b))

replace('docs/metodologia/TRAJETORIAS_INDIVIDUAIS_V1.md',
        'para desenvolvimento. Não contém resultados dessa preparação nem demonstra a\nhipótese sobre a contribuição do fluxo óptico.',
        'para desenvolvimento. As regras prospectivas permanecem abaixo, e os\n[resultados posteriores](#resultados-da-preparação--08092026) estão ao final.\nEsta preparação não demonstra a hipótese sobre a contribuição do fluxo óptico.')
replace('docs/metodologia/TRAJETORIAS_INDIVIDUAIS_V1.md',
        'Os pontos de entrada previstos para implementação são:', 'Os pontos de entrada implementados são:')
table='\n'.join(f"| {v['video_id']} | {fmt(v['individual_observations'])} | {v['segments_total']} | "
    f"{fmt(v['windows_total'])} | {fmt(v['origins_excluded_incomplete_future'])} |" for v in m['summary']['videos'])
append('docs/metodologia/TRAJETORIAS_INDIVIDUAIS_V1.md',f'''## Resultados da preparação — 08/09/2026

Preparação **concluída e conferida**, sem ajuste ou avaliação de modelo. O
protocolo e o código foram registrados em `33d191d` antes do acesso às fontes,
após **1.026 testes em 108,58 s**. A run manteve Git limpo e terminou em
151,929874 s, com pico amostrado de RSS de 226,148 MiB. O orçamento foi cumprido;
146.913.962 bytes foram contabilizados antes da gravação do manifesto final.
RAM foi amostrada em 14 pontos, portanto não é um máximo contínuo garantido.

O universo contém **17.640 quadros**, dos quais **17.466 anotados** e **174 sem
anotação**, exclusivamente nas duas lacunas já registradas do vídeo 23.
Foram preservadas as 368.487 observações brutas: **363.074 individuais**
(347.847 de classe 0 e 15.227 de classe 2) e **5.413 de agrupamentos**.
Os agrupamentos permanecem no CSV bruto e nas contagens; não viram posições
individuais ou máscaras para modelos.

| Vídeo | Observações individuais | Segmentos | Janelas 20+10 | Origens sem futuro completo após histórico válido |
|---|---:|---:|---:|---:|
{table}
| **Total descritivo** | **363.074** | **725** | **343.776** | **6.384** |

Há 669 pares distintos `(vídeo, ID individual original)` e 725 segmentos
contínuos. Esses números descrevem IDs observados, não demonstram identidade
biológica perfeita. **623 segmentos têm janela; 102 não têm**, e todos foram
guardados. Os 102 sem janela contêm **1.231 observações**: 77 segmentos têm
menos de 20 observações e 25 têm entre 20 e 29. Nenhum foi apagado para melhorar
a cobertura ou o desempenho de um algoritmo.

A contabilidade de origens fecha exatamente:

`363.074 = 12.914 sem histórico + 6.384 sem futuro + 343.776 janelas aceitas`.

Entre as 350.160 origens com histórico completo, 6.384 não têm dez posições
futuras: 2.244 por fim do vídeo, 20 por ausência de anotação e 4.120 por
ausência do ID. Os segmentos terminaram 229 vezes na borda do vídeo, duas em
lacunas de anotação e 494 por ausência do ID. **Não houve fronteira de classe
1 do mesmo ID nesta referência de treino**; esse ramo foi verificado por
testes sintéticos. Isso não demonstra ausência de oclusões ou agrupamentos
e não permite inferir a causa biológica de `id_absent`.

### Conferência e limites

A conferência independente passou **na primeira execução**, verificando
**86 arquivos** (85 artefatos e o manifesto) e **9.407.090 comparações de
campos/valores**, em 26,3672 s. Uma implementação por agrupamento offline de
índices consecutivos de cada ID reconstruiu todos os segmentos e janelas a
partir de `ground_truth_raw.csv` e `frame_status.csv`. Observações, classes,
coordenadas em ponto flutuante, IDs, razões e resumos coincidiram integralmente.

O executor leu anotações, hashes e metadados dos MP4 apenas do treino e
reconferiu fontes, inventários, artefatos e proveniência antes de completar.
Não decodificou pixels, não executou detector/tracker e não abriu as fontes de
validação/teste. A conferência independente leu somente os derivados; não
constitui uma segunda releitura das fontes nem uma certificação de identidade
biológica. Janelas continuam dependentes dentro do vídeo e condicionadas à
disponibilidade de referência individual futura. Nenhum ADE/FDE, HOTA ou ganho
de fluxo foi medido neste marco.

### Onde navegar

- [Manifesto da run](../../{batch.as_posix()}/manifest.json),
  [resumo completo](../../{batch.as_posix()}/summary.json) e
  [pastas dos 12 vídeos](../../{batch.as_posix()}/by_video).
- [Conferência independente](../../{qa_path.as_posix()}).
- [Figura PNG](../../{figure.as_posix()}/trajetorias_individuais_treino.png),
  [SVG](../../{figure.as_posix()}/trajetorias_individuais_treino.svg) e
  [revisão visual estática](../../{figure.as_posix()}/visual_review.json).

Cada pasta de vídeo contém exatamente sete arquivos: `ground_truth_raw.csv`,
`observations.csv`, `segments.csv`, `windows.csv`, `frame_status.csv`,
`summary.json` e `input_contract.json`. As fontes permanecem em seu local;
a preparação é derivada e recriável. IDs originais ficam em `track_id` e os
trechos consecutivos em `segment_id`. Os índices atuais ainda precisam ser
integrados aos consumidores de predição, com controle causal e ADE denso.

SHA-256 do manifesto: `{q['run_manifest_sha256']}`.
SHA-256 da conferência: `{sha256_file(ROOT/qa_path)}`.

### Próximo marco

Implementar o consumo desses índices comuns pelos baselines de persistência
e velocidade constante, separando entradas até `t` de alvos futuros e
calculando ADE em todos os passos `1..H`. Verificar primeiro com casos
analíticos e registrar o plano antes da execução real. O contrato de tracking
com IDs originais e HOTA permanece uma etapa própria; o acoplamento de fluxo
e a comparação com/sem fluxo vêm após os controles de causalidade e pareamento.
Teste e folds continuam bloqueados pelo desenho confirmatório pendente.''')
replace('docs/projeto/MATRIZ_EXPERIMENTOS.md',
    '| Seleção de validação | T218/o0/c2: F1 macro 0,658959; T219: 0,657819; sem congelamento, teste ou folds |',
    '| Seleção de validação | T218/o0/c2: F1 macro 0,658959; T219: 0,657819; a bateria precedeu o congelamento de desenvolvimento |')
replace('docs/projeto/MATRIZ_EXPERIMENTOS.md',
    '| Próximo marco | Preparar referência individual do treino e índices de janelas 20+10, sem modelo; depois contrato de tracking e predição causal |',
    '| Referência individual do treino | Concluída em 33d191d: 363.074 observações, 725 segmentos, 343.776 janelas; 86 arquivos conferidos |\n| Próximo marco | Consumir índices comuns nos baselines de predição com ADE denso e entradas causais; contrato HOTA próprio ainda pendente |')
replace('docs/projeto/MATRIZ_EXPERIMENTOS.md','## Predição\n',
    '## Predição\n\nA [referência individual v1](../metodologia/TRAJETORIAS_INDIVIDUAIS_V1.md#resultados-da-preparação--08092026)\nfoi preparada e conferida somente no treino: 363.074 observações, 725 segmentos\ne 343.776 janelas. Isso prepara os dados; as colunas de avaliação dos modelos\nabaixo continuam pendentes. Os 102 segmentos sem janela foram preservados.\n')
replace('README.md','[trajetórias individuais de referência](docs/metodologia/TRAJETORIAS_INDIVIDUAIS_V1.md) no treino.',
    '[trajetórias individuais de referência](docs/metodologia/TRAJETORIAS_INDIVIDUAIS_V1.md) no treino.\n   Essa preparação já foi concluída e conferida: 363.074 observações preservadas\n   e 343.776 janelas; o próximo passo implementa seu consumo pelos preditores.')
replace('README.md','O próximo marco prepara\n   [trajetórias individuais',
    'O protocolo define\n   [trajetórias individuais')
replace('docs/metodologia/VALIDACAO_THRESHOLD_V3.md',
    'com T218/o0/c2 selecionada, ainda sem congelamento. O protocolo prospectivo',
    'com T218/o0/c2 selecionada. Depois, foi registrado seu\n[congelamento para desenvolvimento](CONGELAMENTO_THRESHOLD_V3.md), sem liberar\nteste ou folds. O protocolo prospectivo')
replace('docs/metodologia/VALIDACAO_THRESHOLD_V3.md',
    'O resultado é uma **seleção de validação ainda não congelada**. Não houve\nteste, folds ou nova busca após observar estes resultados. A hipótese de\npredição com fluxo continua pendente. O próximo marco é registrar critérios\nde congelamento e o contrato de trajetórias individuais, preparando tracking\ncom GT e janelas causais comuns para a futura ablação.',
    'Ao concluir a bateria, o resultado era uma **seleção de validação ainda não\ncongelada**. Posteriormente, o [congelamento para desenvolvimento](CONGELAMENTO_THRESHOLD_V3.md)\nfixou T218 sem teste, folds ou nova busca. A [referência individual do treino](TRAJETORIAS_INDIVIDUAIS_V1.md)\nfoi preparada para as janelas comuns da futura ablação. A hipótese de\npredição com fluxo continua pendente.')
append('docs/projeto/DIARIO.md',f'''## 2026-09-08 — nível 5 concluído: referência individual do treino

Preparação em `33d191d`, Git limpo, sem mudança de código durante a execução.
151,929874 s, RSS amostrado 226,148 MiB. Fontes originais preservadas; nenhum
acesso às fontes de validação/teste ou decodificação de pixels neste marco.
Resultado: 17.640 quadros, 17.466 anotados, 174 lacunas; 363.074 observações
individuais, 5.413 clusters brutos, 725 segmentos e 343.776 janelas 20+10.
Os 102 segmentos sem janela conservam 1.231 observações. As origens excluídas
são 12.914 por histórico incompleto e 6.384 por futuro incompleto.

Conferência independente aprovada na primeira execução: 86 arquivos,
9.407.090 comparações, 26,3672 s, reconstrução completa de segmentos/janelas.
Nenhuma transição direta do mesmo ID para classe 1 apareceu na referência;
a regra continua coberta por testes sintéticos, sem inferir a causa das ausências.
A figura descritiva PNG/SVG foi renderizada e o PNG foi conferido visualmente.
Detalhes e caminhos no [protocolo com resultados](../metodologia/TRAJETORIAS_INDIVIDUAIS_V1.md#resultados-da-preparação--08092026).

Run: `{batch.as_posix()}`.
Conferência: `{qa_path.as_posix()}`.
Nenhum modelo temporal foi avaliado. Próximo: consumo de índices comuns,
ADE denso e causalidade nos baselines; contrato HOTA separado e hipótese de
fluxo ainda pendentes. HTML, guia permanente, instruções locais e fonte LaTeX
foram atualizados localmente; o PDF não foi recompilado.''')
append('docs/algoritmos/predicao/README.md','''## Referência individual preparada, sem avaliação de modelos

O [contrato v1 e seus resultados](../../metodologia/TRAJETORIAS_INDIVIDUAIS_V1.md#resultados-da-preparação--08092026)
registram 363.074 observações e 343.776 janelas do treino, conferidas
independentemente. São índices comuns de elegibilidade, ainda sem resultados
dos preditores. O executor antigo de CSV não constitui automaticamente essa
comparação: precisa consumir os segmentos, separar alvos de entradas e
usar ADE denso em 1..H. Os 102 segmentos curtos foram preservados.''')
replace('monografia/cap_metodo/metodo.tex',
    'A seleção ainda não foi congelada e não constitui teste independente, avaliação de folds ou evidência sobre a hipótese de fluxo.',
    'Na conclusão da bateria, a seleção ainda não estava congelada e não constituía teste independente, avaliação de folds ou evidência sobre a contribuição do fluxo. Posteriormente, T218/o0/c2 foi fixada como linha de base de desenvolvimento, com parâmetros e avaliação preservados. Esse escopo mantém teste, folds e aplicação bloqueados até um desenho confirmatório próprio, sem restaurar a cegueira historicamente perdida.')
needle='\\section{Predição das trajetórias}'
addition='''

Antes dos preditores, foi registrado e executado o protocolo de referência individual apenas nos 12 vídeos de treino, sob o commit \\texttt{33d191d}, com Git limpo e 1.026 testes aprovados. As classes 0 e 2 preservam o ID original; classe 1, ausência do ID e ausência de anotação interrompem os segmentos. Mudanças entre classes 0 e 2 não interrompem o trecho. A segmentação não renumera identidades biológicas e não define implicitamente a política de HOTA. Todas as observações e todos os segmentos são mantidos, inclusive os curtos.

Foram preservadas 363.074 observações individuais em 725 segmentos, dos quais 623 geram 343.776 janelas de 20 posições observadas e dez posições futuras, com passo de um quadro. Os 102 segmentos sem janela conservam 1.231 observações. Das origens individuais, 12.914 não têm histórico completo e 6.384 têm histórico, mas não o futuro completo. A elegibilidade é condicionada à disponibilidade de referência individual futura; esse uso é exclusivo dos alvos e da avaliação retrospectiva, não das entradas do preditor. As janelas permanecem dependentes dentro do vídeo. A conferência independente reconstruiu todas as observações, segmentos e janelas a partir dos derivados, verificando 86 arquivos e 9.407.090 comparações. A preparação levou 151,929874 segundos, com pico amostrado de RSS de 226,148 MiB, sem decodificar pixels, avaliar modelos ou abrir fontes de validação e teste. Não houve transição direta de um ID individual para classe 1 nesta referência de treino; a regra foi verificada sinteticamente e não permite inferir a causa biológica de ausências. O consumo dos índices, a causalidade das entradas e a avaliação densa de ADE permanecem para a etapa seguinte.
'''
replace('monografia/cap_metodo/metodo.tex',needle,needle+addition)
print('Public results and local LaTeX source updated; PDF not rebuilt.')
