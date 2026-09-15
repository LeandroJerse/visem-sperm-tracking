from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def replace(name, old, new):
    p = ROOT/name
    data = p.read_bytes()
    old = old.replace('\n','\r\n').encode() if b'\r\n' in data else old.encode()
    new = new.replace('\n','\r\n').encode() if b'\r\n' in data else new.encode()
    assert data.count(old)==1,(name,data.count(old))
    p.write_bytes(data.replace(old,new))
def append(name, text):
    p=ROOT/name
    with p.open('a',encoding='utf-8',newline='\n') as out: out.write('\n'+text+'\n')

replace('README.md','foi congelada no novo contrato.',
        'foi liberada para confirmação. A [T218 v3 congelada para desenvolvimento](configs/frozen/detection/threshold/t218_o0_c2_v3.yaml)\n   fixa os parâmetros e mantém teste/folds bloqueados. O próximo marco prepara\n   [trajetórias individuais de referência](docs/metodologia/TRAJETORIAS_INDIVIDUAIS_V1.md) no treino.')
replace('docs/algoritmos/deteccao/threshold_fixo.md',
        '**T218/o0/c2 foi selecionada na validação**, sem congelamento ou teste.',
        '**T218/o0/c2 está congelada para desenvolvimento**, após a seleção na validação.\nO [registro de congelamento v3](../../metodologia/CONGELAMENTO_THRESHOLD_V3.md)\nfixa parâmetros e avaliação; teste e folds continuam bloqueados.')
replace('docs/metodologia/PROTOCOLO.md',
        'estão separados das regras prospectivas. O desenho confirmatório continua pendente.',
        'estão separados das regras prospectivas. Posteriormente, o\n[congelamento para desenvolvimento](CONGELAMENTO_THRESHOLD_V3.md) fixou T218\nsem liberar teste/folds. A [referência de trajetórias individuais v1](TRAJETORIAS_INDIVIDUAIS_V1.md)\né preparada somente no treino. O desenho confirmatório continua pendente.')
replace('docs/projeto/MATRIZ_EXPERIMENTOS.md',
        '| Próximo marco | Registrar critérios de congelamento e contrato de trajetórias individuais; preparar tracking com GT e janelas causais comuns |',
        '| Congelamento v3 | T218/o0/c2 fixa para desenvolvimento; teste e folds bloqueados pelo escopo executável |\n| Próximo marco | Preparar referência individual do treino e índices de janelas 20+10, sem modelo; depois contrato de tracking e predição causal |')
append('script/README.md','''## Referência de trajetórias individuais do treino

Plano: [individual_trajectories_v1.yaml](../configs/protocol/individual_trajectories_v1.yaml).
Contrato: [trajetórias individuais v1](../docs/metodologia/TRAJETORIAS_INDIVIDUAIS_V1.md).
Executar somente com Git limpo, após os testes do código:

```powershell
.venv/Scripts/python.exe -X utf8 -B -m script.prediction.test.prepare_ground_truth
```

O comando não aceita substituição de split, vídeo ou parâmetros. Prepara os
12 vídeos de treino registrados, preserva GT bruto e observações 0/2, separa
segmentos contínuos e exporta índices de janelas 20+10. Não executa modelo,
fluxo ou métrica de predição. Só consulta metadados e hash do MP4; não certifica
decodificação integral de pixels. A run nova fica sob
`data/derived/prediction/ground_truth_individuals/`, com `manifest.json`,
`summary.json` e sete artefatos em `by_video/<id>/`. Falhas ficam preservadas.

O [T218 congelado para desenvolvimento](../configs/frozen/detection/threshold/t218_o0_c2_v3.yaml)
é a referência de detecção v3. Seu escopo bloqueia teste, folds e aplicação,
mesmo quando uma chamada tenta trocar flags ou o arquivo de splits.''')
append('configs/README.md','''## Linha de base v3 e trajetórias individuais

- [T218/o0/c2 v3](frozen/detection/threshold/t218_o0_c2_v3.yaml): parâmetros
  fixos para desenvolvimento; teste/folds não liberados. A seleção original
  e os hashes da conferência permanecem registrados.
- [Referência individual v1](protocol/individual_trajectories_v1.yaml): coorte
  de treino, regras de segmentação, histórico 20, futuro 10 e orçamento,
  registrados antes da preparação. Não é configuração de um preditor.''')
append('src/prediction/README.md','''## Referência individual antes dos modelos

[ground_truth.py](ground_truth.py) preserva observações GT 0/2 e o ID original,
gera segmentos contínuos e índices de janelas. O código é puro: não abre arquivos,
executa modelo ou usa fluxo. Segmento não é uma nova identidade biológica.
Consulte o [contrato v1](../../docs/metodologia/TRAJETORIAS_INDIVIDUAIS_V1.md)
e os [comandos oficiais](../../script/README.md#referência-de-trajetórias-individuais-do-treino).
O consumo desses índices pelos preditores e o ADE denso por horizonte continuam
pendentes; o executor antigo não deve ser apresentado como essa comparação.''')
append('docs/README.md','''## Marco atual: linha de base e referência individual

- [Congelamento do threshold v3 para desenvolvimento](metodologia/CONGELAMENTO_THRESHOLD_V3.md).
- [Referência de trajetórias individuais v1](metodologia/TRAJETORIAS_INDIVIDUAIS_V1.md).''')
append('docs/projeto/DIARIO.md','''## 2026-09-08 — linha de base fixa e protocolo de referência individual

Após a autorização para continuar, T218/o0/c2 foi materializada como configuração
congelada para desenvolvimento, sem nova busca nem acesso às fontes. Foram
reconferidos 46 artefatos da validação, seus pais e a identidade dos componentes
de detecção/avaliação. As runs continuam atribuídas a 7f47afb; o recibo de decisão
fica em `data/derived/project_audits/general_20260908/freeze_t218_development_20260908.json`.
O escopo executável bloqueia teste/folds e não restaura a cegueira histórica.

Registrado o protocolo de referência individual do treino: classes 0/2,
IDs originais, interrupções explícitas, todos os segmentos preservados,
janelas 20+10/stride 1 e exclusões por falta de futuro contabilizadas.
Módulo puro, executor e testes sintéticos precedem a primeira preparação.
A preparação real e sua conferência serão registradas em entrada separada.
Não há neste marco resultado de rastreamento, fluxo ou predição.''')
