# Revisão geral de alinhamento e integridade — 08/09/2026

## Parecer e alcance

O projeto continua alinhado ao tema **Análise e Predição de Trajetórias de
Espermatozoides em Vídeos Microscópicos**. Não há fundamento, nesta revisão,
para recomeçar o trabalho ou descartar a busca de threshold já concluída.
A organização e as evidências existentes permitem continuar, com os controles
pendentes descritos abaixo. Isso não equivale a certificar toda a pipeline ou
a considerar demonstrada a hipótese central.

Foram comparados o texto acadêmico atual, o protocolo, a matriz experimental,
as evidências de execução e o projeto assinado original, disponível apenas
neste caminho local: [PDF assinado](<C:/Users/leand/Documents/ufu/2026_01/TCC/trab5/Analise_e_Predicao_de_Trajetorias_de_Espermatozoides_em_Videos_Microscopicos__1__assinado_assinado.pdf>).
O PDF é evidência documental; não foi alterado nem copiado para o repositório.
Esta revisão não abriu pixels ou anotações das divisões de validação e teste.

O núcleo científico permanece: comparar preditores equivalentes que recebem
posição, histórico e velocidade, com e sem características locais de fluxo
óptico, usando ADE e FDE. Detecção e rastreamento são etapas necessárias à
avaliação fim a fim. O threshold é uma linha de base de localização; sua
seleção não testa, por si só, a contribuição do fluxo à predição.

## Evidências verificadas e limites

O [relatório de integridade e testes](../../data/derived/project_audits/general_20260908/integrity_and_tests.json)
registra estado aprovado, 3.248 arquivos únicos conferidos e 17.753
conferências, incluindo hashes e consistência dos artefatos. A suíte executada
passou em 502 testes, sem falhas, em 100,33 segundos, excluindo os grupos
`optional_ml` e `slow`. A análise sintática adicional de 153 arquivos Python
também foi aprovada. Sintaxe válida e testes aprovados não substituem
avaliação científica nem certificam ambientes opcionais de aprendizagem.

A auditoria conferiu hashes dos 12 MP4 de treino, dos 12 arquivos de cache e
das 576 anotações selecionadas, sem nova decodificação ou execução do detector.
Conferiu ainda a integridade das evidências da revisão independente do
refinamento; não repetiu todas as suas associações. A separação dos folds foi
verificada como partição de IDs, sem certificar um desenho completo de seleção
e avaliação fora da amostra.

A triagem e o refinamento do threshold v3 estão concluídos e conferidos.
O refinamento avaliou 117 candidatos nos mesmos 576 quadros físicos de treino,
48 por vídeo, totalizando 67.392 avaliações de configuração–quadro.
T219/o0/c2 e T218/o0/c2 são finalistas **de treino**. A conferência independente
registrou 4.029.280 comparações de campos/valores, 162 verificações de matching
e consistência em 720 pares configuração–quadro compartilhados com a triagem.
Esses 720 pares correspondem a cinco configurações nos mesmos 144 quadros
físicos, não a 720 observações independentes.

Os estados por algoritmo permanecem na [matriz experimental](MATRIZ_EXPERIMENTOS.md),
e a sequência das evidências está no [diário](DIARIO.md). Resultados do piloto
histórico e do contrato de 15 px continuam separados da avaliação v3.

## Ajustes legítimos em relação ao projeto assinado

| Decisão atual | Relação com o objetivo original |
|---|---|
| Usar exclusivamente VISEM/VISEM-Tracking | Corrige a associação indevida desses vídeos a uma segunda aquisição com tubo; mantém a análise microscópica e a hipótese de predição. |
| Tratar fluxo como movimento aparente | Evita concluir velocidade física do fluido sem referência física correspondente. |
| Fixar IDs de treino/validação/teste e registrar a exposição histórica | Torna operacional a separação por vídeo prevista no projeto, sem simular cegueira retrospectiva. |
| Definir F1 de indivíduos a 10 px, sensibilidades e política para agrupamentos | Especifica a localização necessária à pipeline; não transforma esse critério em mAP publicado nem em erro de anotação conhecido. |
| Fixar histórico de 20 quadros e horizontes de 1, 5 e 10 | Concretiza as janelas antes genéricas, ainda sujeitas aos controles de elegibilidade e causalidade. |
| Expandir o catálogo de métodos clássicos, aprendidos e híbridos | É uma extensão de escopo; deve permanecer subordinada à conclusão da ablação central. |

A documentação primária descreve o [VISEM](https://datasets.simula.no/visem/)
com 85 vídeos publicados e o [VISEM-Tracking](https://www.nature.com/articles/s41597-023-02173-4)
com trechos anotados de 20 participantes. As condições de aquisição descritas
não documentam tubo ou contracorrente induzida. A correção retira essa premissa;
não demonstra ausência de todo movimento do fluido nas imagens. Os 65 vídeos
sem tracking manual destinam-se à aplicação qualitativa posterior. Clipes
extraídos das mesmas aquisições não aumentam a independência amostral.

O artigo do VISEM-Tracking distingue indivíduos normais, indivíduos pequenos e
agrupamentos e publica avaliação de detecção por AP/IoU. Nossa regra espacial
de centros é uma decisão operacional documentada em
[classes e agrupamentos](../metodologia/CLASSES_E_AGRUPAMENTOS.md) e
[tolerância espacial](../metodologia/TOLERANCIA_ESPACIAL.md). Não há, nas fontes
consultadas, uma estimativa de erro entre anotadores que determine que 10 px
seja a tolerância ótima para este conjunto.

## Achados materiais e controles antes das próximas etapas

| Prioridade | Achado | Controle e estado nesta revisão |
|---|---|---|
| Antes da validação | Um leitor permissivo pode aceitar vídeo incompleto, GT malformado ou proveniência insuficiente. | Contrato estrito e coordenador específico implementados após a auditoria, com testes de EOF, GT, métricas exportadas e adulteração de artefatos. O fluxo legado permanece disponível; a bateria usa obrigatoriamente o novo contrato. A execução depende do commit e da aprovação dos testes registrados no diário. |
| Antes da ablação | Executar dois métodos isoladamente não certifica o mesmo universo de janelas. | Registrar um manifesto comum de janelas elegíveis e comparar as mesmas chaves vídeo/ID/instante/horizonte. Contabilizar exclusões comuns e falhas por método. |
| Antes da ablação | Fluxo calculado após o instante de previsão pode revelar o futuro. | Limitar imagens, máscaras e características de entrada a instantes até `t`; usar o futuro apenas como alvo. Controles com informação futura devem ser identificados como oráculo, fora da comparação principal. |
| Antes de tracking/predição | Uma caixa de agrupamento não representa necessariamente uma célula individual. | Definir elegibilidade de trajetórias das classes 0/2 e política explícita para agrupamentos, IDs e lacunas. Não transferir automaticamente o raio de detecção ao HOTA oficial. |
| Antes de reportar ADE | A API atual calcula a média dos instantes fornecidos; fornecer apenas 1/5/10 não calcula ADE de 1 a 10. | Para cada horizonte H, produzir os erros em todos os passos de 1 a H e sua média; nomear separadamente qualquer média de horizontes esparsos. |
| Antes da inferência final | O holdout contém somente quatro vídeos e já teve exposição no piloto. | Priorizar diferenças por vídeo, divulgar a exposição e limitar a interpretação inferencial; ver ressalva estatística abaixo. |
| Gestão do escopo | O catálogo ampliado pode consumir o tempo necessário à hipótese central. | Priorizar a pipeline mínima verificável e a comparação causal com/sem fluxo antes de variantes adicionais. |

Para a predição, histórico, máscara e normalização também precisam respeitar o
limite temporal e a separação entre treino e avaliação. Ausência de fluxo
válido não equivale a vetor zero. Uma falha de um método não pode retirar
silenciosamente apenas suas janelas difíceis: cobertura e exclusões devem
acompanhar os erros. O cenário com trajetórias anotadas isola o preditor; o
cenário com trajetórias estimadas mede a propagação de erros da pipeline.

A definição operacional a adotar, com erro euclidiano `e_h` no passo futuro h,
é `ADE_H = (e_1 + ... + e_H) / H` e `FDE_H = e_H`. Essa definição deverá ser
conferida no produtor e no avaliador de janelas antes de receber resultados
científicos. A referência de predição inclui
[Social LSTM](https://www.cv-foundation.org/openaccess/content_cvpr_2016/papers/Alahi_Social_LSTM_Human_CVPR_2016_paper.pdf);
o protocolo deste trabalho explicita quais passos e unidades entram na média.

No Wilcoxon bilateral exato, com quatro diferenças independentes, não nulas e
sem empates nos módulos, o menor p possível é `2 / 2^4 = 0,125`. Esse limite
decorre das 16 atribuições de sinais: mesmo quatro diferenças na mesma direção
não permitem atingir 5% nesse teste. A [documentação do SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html)
explicita as hipóteses e o tratamento do método exato. Seeds, frames e
trajetórias não resolvem essa limitação, pois não criam novos vídeos.

Intervalos por bootstrap de quatro vídeos, se futuramente apresentados, serão
exploratórios e acompanhados dos quatro valores/diferenças. Usar os 20 vídeos
em avaliação fora da amostra exige seleção e ajuste dentro dos folds de treino
de cada avaliação externa; repetir uma configuração já selecionada não basta.
Essa exigência decorre do risco de viés de seleção descrito por
[Cawley e Talbot](https://www.jmlr.org/papers/volume11/cawley10a/cawley10a.pdf),
e não apaga a exposição histórica. A
[política estatística](../metodologia/ESTATISTICA_E_PARETO.md) detalha os limites.

## Próximos marcos e critério de continuidade

1. Finalizar, testar e registrar em commit o executor e o
   [protocolo de validação das duas finalistas](../metodologia/VALIDACAO_THRESHOLD_V3.md).
   A bateria será de oito pares configuração–vídeo, com 11.700 avaliações de
   quadros; a seleção não congela automaticamente uma configuração.
2. Consolidar elegibilidade individual e avaliação de associação, primeiro com
   caixas anotadas e depois com detecções selecionadas. Registrar o que cada
   cenário isola, sem confundir tracking com detecção.
3. Construir o conjunto comum de janelas e verificar causalidade e ADE/FDE com
   casos sintéticos. Estabelecer persistência/velocidade constante e uma
   comparação equivalente com fluxo aparente local, começando por Farnebäck.
4. Executar a ablação principal com trajetórias anotadas e depois a avaliação
   fim a fim. Incorporar o preditor aprendido e o detector aprendido com
   ambiente, orçamento e critérios próprios; variantes extras vêm depois.
5. Antes de qualquer etapa confirmatória, registrar o desenho de seleção,
   congelamento e avaliação e declarar a exposição histórica do teste.

A primeira bateria prospectiva após esta revisão continua sendo a validação
do threshold, restrita a quatro vídeos e às duas finalistas de treino. Nenhuma
conclusão sobre a hipótese de fluxo foi obtida nesta revisão. Um resultado sem
ganho de fluxo também poderá responder ao TCC, desde que a comparação seja
pareada, causal, reproduzível e interpretada com seus limites.
