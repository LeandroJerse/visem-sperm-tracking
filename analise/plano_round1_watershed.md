# Watershed — plano do round1

## Escopo e situação

**Registro do desenho anterior à execução.** O round1 foi executado pelo
pesquisador e [conferido](analise_round1_watershed.md). As justificativas
abaixo preservam as hipóteses anteriores à observação desses resultados.
O round0 validou caixas, áreas, centroides, anotações normalizadas, métricas
e integridade. Seu [diagnóstico](diagnostico_round0_watershed.md) fundamenta
esta busca ampla de **48 configurações × 178 quadros = 8.544 avaliações**.

O detector, a caixa envolvente dos pixels, o avaliador e os resultados do
round0 permanecem iguais. Agora variam os parâmetros de segmentação,
sementes, filtro de área e preservação de aglomerados.

## Por que este desenho

- **Quatro controles claros:** r1c01–r1c04 repetem exatamente w01–w04.
  Nos seis quadros comuns ao round0, o executor exige igualdade de quatro
  arquivos por caso: previsões, detecções, avaliação e diagnóstico.
  São 24 casos e 96 comparações de hash. Tempo de execução e imagens com ID
  no título não entram nessa igualdade.
- **36 explorações claras:** filtros de área, sementes e morfologia incluem
  contrastes dirigidos; seis limiares manuais exploram combinações mais amplas.
  A polaridade clara encontrou 83 dos 167 indivíduos no melhor controle,
  mas ainda produziu muitos falsos positivos.
- **Oito explorações escuras:** limiares manuais baixos, entre 40 e 100,
  investigam objetos perdidos pela máscara clara. Otsu escuro foi removido
  desta busca porque cobriu quase todo o fundo na inspeção.
- **24 pares:** cada base usa separar e preservar por área, mantendo os
  demais parâmetros idênticos. Assim se mede o efeito dessa política em
  cada contexto; não se escolhe uma regra antes da rodada.

Os valores são hipóteses de exploração, não limites estimados com precisão.
O round0 contém apenas seis quadros e sete pequenos; não justifica
afirmar que uma faixa de tamanho já está validada.

## Parâmetros fixos e variáveis

Permanecem fixos: conectividade 8, área máxima aceita 5.000 pixels²,
classe pequeno até 120 pixels² e representação das caixas.
A área mínima de aglomerado é 600, 900 ou 1.200; a área entre os dois
limites de classe representa normal. O filtro mínimo de detecção é
independente do limite de classificação.

A área mínima de 3 permanece nos controles e numa base escura. Valores
12, 24, 48 e 72 investigam a rejeição de ruído sem começar diretamente em
95, que seria uma extrapolação excessiva do menor acerto visto na inspeção.

Frações de semente 0,35, 0,50, 0,75 e 0,90 exploram a geometria dos núcleos.
Uma fração maior não garante mais ou menos objetos em todas as imagens.

Abertura e fechamento desligados ou com elementos de 3×3 e 5×5 investigam
ruído, união e preenchimento das regiões. A área mínima e as sementes têm
contrastes em que só um eixo muda. A morfologia é comparada com limiar Otsu,
semente 0,75, área mínima 24 e limite de aglomerado 900 fixos.

Os limiares manuais claros 100, 125, 150, 175, 200 e 225 cobrem uma faixa
ampla de intensidade. Nessa parte, áreas, sementes, limites de aglomerado
e perfis morfológicos são balanceados e embaralhados por seed 42.
A busca escura usa o mesmo mecanismo com seus quatro níveis.
**As configurações conjuntas não isolam o efeito de cada variável.**
Não é uma grade completa, um treinamento ou um algoritmo evolutivo:
o próximo refinamento dependerá da análise desta rodada.

Alterar apenas o limite entre classes 0 e 2 não melhora o F1 de localização
adotado, pois ambas pertencem ao mesmo grupo. Esse limite permanece fixo;
erros de classificação continuam registrados.

## Catálogo congelado

Em cada linha, o primeiro ID separa regiões; o segundo preserva componentes
com área de aglomerado. Áreas em pixels². Operações ativas usam uma iteração.

| Par | Configurações | Limiar | Polaridade | Abertura | Fechamento | Semente | Área mínima | Aglomerado a partir de |
|---|---|---|---|---|---|---:|---:|---:|
| p01 | r1c01 / r1c02 | Otsu | claro | desligada | retângulo 5×5, 1 vez | 0.5 | 3 | 900 |
| p02 | r1c03 / r1c04 | Otsu | claro | desligada | retângulo 5×5, 1 vez | 0.75 | 3 | 900 |
| p03 | r1c05 / r1c06 | Otsu | claro | desligada | retângulo 5×5, 1 vez | 0.75 | 12 | 900 |
| p04 | r1c07 / r1c08 | Otsu | claro | desligada | retângulo 5×5, 1 vez | 0.75 | 24 | 900 |
| p05 | r1c09 / r1c10 | Otsu | claro | desligada | retângulo 5×5, 1 vez | 0.75 | 48 | 900 |
| p06 | r1c11 / r1c12 | Otsu | claro | desligada | retângulo 5×5, 1 vez | 0.75 | 72 | 900 |
| p07 | r1c13 / r1c14 | Otsu | claro | desligada | retângulo 5×5, 1 vez | 0.35 | 48 | 900 |
| p08 | r1c15 / r1c16 | Otsu | claro | desligada | retângulo 5×5, 1 vez | 0.9 | 48 | 900 |
| p09 | r1c17 / r1c18 | Otsu | claro | desligada | desligada | 0.75 | 24 | 900 |
| p10 | r1c19 / r1c20 | Otsu | claro | desligada | elipse 3×3, 1 vez | 0.75 | 24 | 900 |
| p11 | r1c21 / r1c22 | Otsu | claro | desligada | retângulo 3×3, 1 vez | 0.75 | 24 | 900 |
| p12 | r1c23 / r1c24 | Otsu | claro | desligada | elipse 5×5, 1 vez | 0.75 | 24 | 900 |
| p13 | r1c25 / r1c26 | Otsu | claro | elipse 3×3, 1 vez | elipse 3×3, 1 vez | 0.75 | 24 | 900 |
| p14 | r1c27 / r1c28 | Otsu | claro | elipse 3×3, 1 vez | retângulo 5×5, 1 vez | 0.75 | 24 | 900 |
| p15 | r1c29 / r1c30 | 100 | claro | desligada | elipse 3×3, 1 vez | 0.75 | 24 | 900 |
| p16 | r1c31 / r1c32 | 125 | claro | desligada | retângulo 3×3, 1 vez | 0.35 | 12 | 600 |
| p17 | r1c33 / r1c34 | 150 | claro | desligada | elipse 5×5, 1 vez | 0.5 | 24 | 900 |
| p18 | r1c35 / r1c36 | 175 | claro | elipse 3×3, 1 vez | elipse 3×3, 1 vez | 0.75 | 48 | 600 |
| p19 | r1c37 / r1c38 | 200 | claro | elipse 3×3, 1 vez | retângulo 5×5, 1 vez | 0.9 | 12 | 1200 |
| p20 | r1c39 / r1c40 | 225 | claro | desligada | desligada | 0.5 | 72 | 1200 |
| p21 | r1c41 / r1c42 | 40 | escuro | desligada | desligada | 0.75 | 12 | 900 |
| p22 | r1c43 / r1c44 | 60 | escuro | elipse 3×3, 1 vez | desligada | 0.5 | 48 | 1200 |
| p23 | r1c45 / r1c46 | 80 | escuro | desligada | elipse 3×3, 1 vez | 0.35 | 24 | 600 |
| p24 | r1c47 / r1c48 | 100 | escuro | elipse 3×3, 1 vez | elipse 3×3, 1 vez | 0.9 | 3 | 900 |

O catálogo detalhado e os hashes estão em
[`round1.json`](../scripts/watershed/rodadas/round1.json).
A [geração](../scripts/watershed/planejamento.py) usa seed 42 e é verificável:
o executor regenera a lista e compara com o plano antes de começar.
O gerador recusa sobrescrever um plano diferente.

## Dados e avaliação

São os mesmos 178 quadros de desenvolvimento das rodadas anteriores:
vídeos 11, 12, 15, 19, 21, 22, 23, 30, 35, 36, 47 e 60; índices
0, 100, …, 1.400, exceto 23/900 e 23/1100, cujas anotações estão ausentes.
Essas duas exclusões continuam documentadas; não se substituem quadros.
Vídeos de seleção e avaliação final não entram no round1.

Métrica principal: F1 de localização dos indivíduos, classes 0+2.
Correspondência exclusiva com IoU ≥ 0,50; aglomerados avaliados separadamente.
Somam-se TP, FP e FN antes de calcular F1. Trocas 0/2 são registradas como
erro de classificação entre indivíduos localizados. Somente TP=FP=FN=0
gera “sem casos”; previsões sem anotações dão F1 zero.

O ranking usa a fração exata e mantém a mesma posição para empates.
A classe 0 não recebe peso ou desempate adicional. O PDF exibe as dez
primeiras e também o ranking completo. Isso não seleciona finalistas.

Relatar resultados por vídeo ajuda a identificar dependência de uma origem.
As configurações compartilham imagens e os quadros de um vídeo são
correlacionados. Quartis no PDF descrevem esta lista de configurações;
não são intervalos de confiança nem evidência de significância estatística.
O histórico de exposição aos dados em versões anteriores permanece válido.

## Reprodutibilidade, saídas e conferências

Antes de executar, o script verifica o plano, 356 imagens/anotações,
96 arquivos de controle, quatro origens e o código preservado do round0.
São 457 origens registradas, contando o plano desta rodada.
NumPy, OpenCV, SciPy e scikit-image devem corresponder às versões do round0.
A execução usa os bytes conferidos e arquiva o código em `codigo.zip`.

Cada batch fica em `resultados/frame-to-frame/watershed/round1/batch__<UTC>/`.
Cada configuração tem uma pasta com ID, limiar, polaridade, semente,
política, área mínima, hash dos parâmetros completos e identificação UTC.
Dentro dela, cada quadro guarda comparação visual, máscara, regiões,
mapas numéricos, caixas, anotações, pares, erros e avaliação.
No batch ficam os resumos por quadro/configuração/vídeo, ranking,
controles, plano, origens e manifesto com hashes.

A identificação legível resume a configuração; o hash distingue também
as escolhas de morfologia e os limites omitidos no nome curto.
O nome e o tempo mudam entre execuções; parâmetros, entradas e saídas
determinísticas dos controles devem permanecer iguais.

Interrupções preservam arquivos parciais e não marcam o batch como concluído.
Nova execução cria outra pasta, sem sobrescrever. Não há retomada automática
de uma execução parcial nesta versão. Se apenas o PDF falhar, ele pode ser
regenerado sem repetir detecções.

O PDF de quatro páginas confere tabelas, agregações, configurações, arquivo
de código, cópias de origem e os 24 controles. As demais mídias têm hashes
registrados, mas não são relidas na geração do PDF. A auditoria completa
da rodada ocorrerá após a execução do pesquisador.

Preparação conferida com 28 testes de geometria, métricas, controles,
execução sintética, falhas e relatório; 457 origens verificadas sem executar
o detector nos dados da pesquisa. As quatro páginas do PDF foram
inspecionadas usando dados fictícios, separados dos resultados da pesquisa.

O [guia de execução](../scripts/watershed/README.md) traz os comandos.
Após o round1, conferir completude e integridade, analisar FP/FN, cobertura
das classes, variação por vídeo e contrastes em pares. Só então definir
o round seguinte, preservando controles. Não foram criados planos futuros.

## Arquivos preparados nesta etapa

- [Geração reproduzível](../scripts/watershed/planejamento.py) e
  [plano congelado](../scripts/watershed/rodadas/round1.json).
- [Executor](../scripts/watershed/executar_rodada.py),
  [gerador do PDF](relatorio_rodada_watershed.py) e
  [testes da rodada](../scripts/testes/test_rodada_watershed.py).
- Este plano e o [guia de watershed](../scripts/watershed/README.md).
- Guias gerais atualizados: [principal](../README.md),
  [scripts](../scripts/README.md), [análise](README.md),
  [clássicos](../algoritmos/classicos/README.md),
  [plano técnico](plano_watershed.md),
  [diagnóstico anterior](diagnostico_round0_watershed.md) e
  [estado da pesquisa](estado_pesquisa.md).

O código do detector, os avaliadores, os planos históricos e os resultados
reais anteriores não foram alterados nesta preparação.
