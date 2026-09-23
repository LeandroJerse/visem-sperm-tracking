# Preparação do round1 de blobs

20/09/2026 — infraestrutura implementada e plano congelado; primeira tentativa
interrompida por falha de gravação. Correção e repetição concluídas, com
resultados na [análise do round1](analise_round1_blobs.md).

Os modos de caixa original/escala/margem, a divisão de 12 controles + 36
exploratórias e os valores abaixo estão implementados no
[plano do round1](../scripts/blobs/rodadas/round1.json). São 48 configurações
distintas nos mesmos 178 quadros, geradas com seed 42. O pesquisador executará
as 8.544 avaliações; a preparação não produz resultados de desempenho.

## Objetivo

Investigar a extensão das caixas e a geração dos candidatos dentro da rodada
formal. O round0 já demonstrou compatibilidade de formato e identificou
caixas pequenas, muitos candidatos excedentes e diferenças entre classes.
Não haverá outro processo extenso de calibração antes do round1.

Manter o avaliador: IoU ≥ 0,50, indivíduos 0/2 juntos, aglomerados separados,
classificação nos pares válidos e F1 calculado após somar TP/FP/FN. Não criar
novos pesos, desempates ou exigências de F1 para iniciar os experimentos.

## 1. Infraestrutura mínima

| Peça | Implementação disponível |
|---|---|
| Conversão de caixas | Módulo próprio em `algoritmos/classicos/caixas_blobs.py`, aplicado às detecções originais |
| Executor | `scripts/blobs/executar_rodada.py`, aceitando uma rodada ou um plano explícito |
| Plano | `scripts/blobs/rodadas/round1.json`, com as 48 configurações completas e os 178 quadros/hash |
| Planejamento | `scripts/blobs/planejamento.py`, com geração balanceada e validação da lista congelada |
| Relatório | `analise/relatorio_rodada_blobs.py`, usando os resultados salvos e permitindo regenerar o PDF |

Os arquivos estão disponíveis. Um único executor atende às rodadas;
round2–round5 serão outros planos, definidos a partir dos resultados e ainda
não preparados. O padrão sem argumentos é round1.

O parser atual de `ConfiguracaoBlobs` exige chaves estritas. Para preservar
o round0, a nova regra de caixa fica separada dos parâmetros do detector
no plano da rodada. Os planos e executores anteriores não precisam ser
reescritos. A conversão consome centro/diâmetro brutos e não recebe anotações.

Regras de caixa, antes do arredondamento e do recorte:

- Original: lado = diâmetro.
- Escala: lado = fator × diâmetro.
- Margem: lado = diâmetro + 2 × margem, pois há acréscimo em cada lado.

Preservar centro, diâmetro, área circular estimada e classe, além de registrar
a caixa original e a utilizada na avaliação. Uma caixa ampliada não muda a
classe automaticamente. Nas variantes de um mesmo detector, preservar a
identificação dos candidatos sem depender de reordenar as caixas adaptadas.
Essa identificação continua restrita ao quadro, sem rastreamento.

## 2. Distribuição congelada: 12 comparativas + 36 exploratórias

| Bloco | Quantidade | Finalidade |
|---|---:|---|
| Referências originais b01/b02 | 2 | Reproduzir o comportamento original nos 178 quadros |
| Alterar somente a caixa das referências | 10 | Isolar o efeito de escala e margem em cada polaridade |
| Exploração de combinações | 36 | Buscar configurações mais eficientes do detector e das saídas |
| Total | **48** | **8.544 avaliações de imagem/configuração** |

### Doze comparações controladas

Manter todos os parâmetros de detecção e classificação do round0. Para cada
polaridade (claro/escuro), comparar seis regras:

| Variante | Regra |
|---|---|
| Original | Lado igual ao diâmetro |
| Escala 2 | Dobrar o diâmetro |
| Escala 3 | Triplicar o diâmetro |
| Escala 4 | Quadruplicar o diâmetro |
| Margem 4 | Acrescentar 4 px de cada lado; 8 px no lado total |
| Margem 8 | Acrescentar 8 px de cada lado; 16 px no lado total |

São duas polaridades × seis variantes = 12, incluindo as duas referências.
Nesse bloco, os candidatos e as classes permanecem os mesmos por polaridade;
as diferenças nas correspondências decorrem das caixas utilizadas. A conclusão
não se estende automaticamente a todos os demais parâmetros de detecção.

### Trinta e seis combinações exploratórias

Separar em seis grupos: claro/escuro × original/escala/margem. Gerar seis
configurações em cada grupo. Isso mantém 24 configurações de cada polaridade
na rodada completa, sem descartar a escura pelos resultados de seis imagens.

Somando os dois blocos, há 14 caixas originais, 18 com escala e 16 com
margem. O pequeno desequilíbrio é intencional: o bloco controlado testa três
escalas e duas margens. As 36 exploratórias são equilibradas entre os modos.

## 3. Valores candidatos da exploração

| Parâmetro | Valores do espaço de exploração | Motivo |
|---|---|---|
| Limiar mínimo | 10, 40, 80 | Explorar diferentes inícios da faixa de intensidade |
| Limiar máximo, exclusivo | 180, 220, 250 | Comparar faixas menores com a faixa ampla original |
| Passo do limiar | 5, 10, 20 | Variar a densidade da exploração de intensidades |
| Repetibilidade mínima | 2, 3, 4 | Investigar persistência e rejeição de respostas ocasionais |
| Distância mínima | 3, 6, 12 px | Investigar agrupamento, observando possível fusão de vizinhos |
| Área interna mínima | 3, 8, 16, 32 px² | Explorar a rejeição de estruturas muito pequenas |
| Área interna máxima, exclusiva | 500, 1.500, 5.000 px² | Comparar limites restritivos e amplos para regiões grandes |
| Escala, quando ativa | 1,5; 2; 2,5; 3; 4 | Explorar ampliações de intensidades diferentes |
| Margem, quando ativa | 2, 4, 6, 8 px por lado | Explorar correção aditiva, especialmente relevante para blobs pequenos |
| Limite de pequeno | Diâmetros equivalentes 4, 6, 8, 10 px | Examinar a classificação sem presumir que o limite original é adequado |
| Início de aglomerado | Diâmetros equivalentes 16, 24, 32 px | Examinar o limite entre indivíduo e aglomerado |

Os limites da classificação estão gravados como áreas circulares estimadas,
calculadas por π × (diâmetro / 2)². Os diâmetros da tabela apenas facilitam a
interpretação dos parâmetros. Não são limites biológicos medidos na base.
Área interna do filtro, área circular estimada e área da caixa são distintas;
não transferir valores entre elas como se fossem equivalentes.

Para forma, distribuir um perfil de cada tipo em cada grupo de seis:

1. Sem filtro de forma.
2. Circularidade mínima 0,4.
3. Circularidade mínima 0,6.
4. Inércia mínima 0,2.
5. Inércia mínima 0,4.
6. Convexidade mínima 0,8.

Assim, cada perfil aparece seis vezes na exploração. Não combinar os três
filtros simultaneamente nesta primeira busca. Esses cortes são hipóteses de
sondagem; a inspeção disponível não permite estimá-los como valores ideais.

A amplitude das caixas se apoia no diagnóstico: entre anotações individuais
com um centro, a mediana da razão entre área prevista e anotada foi 17,50%
em b01 e 9,21% em b02.
Isso justifica investigar ampliações, mas não determina um fator correto.
Ampliar também pode piorar a sobreposição, abranger vizinhos ou aumentar
caixas sobre candidatos indevidos. Os limites de filtros e intensidades
representam exploração de parâmetros, não quantis medidos de objetos reais.

## 4. Como montar a lista reproduzível

Procedimento implementado: amostragem balanceada por grupo, com seed 42 e
lista explícita salva. O plano registra versão e hash do gerador, versão do
Python, ordem dos grupos/campos, valores candidatos e tentativas por grupo.

1. Inserir as 12 comparações controladas, preservando referência aos parâmetros b01/b02.
2. Usar ordem fixa dos seis grupos de polaridade/modo e dos campos do gerador.
3. Em cada grupo, distribuir os seis perfis de forma uma vez cada.
4. Para cada outro parâmetro, distribuir os valores candidatos de modo tão
   equilibrado quanto possível em seis posições; sortear os valores extras
   e embaralhar as posições com o gerador local de seed 42.
5. Aplicar parâmetros de tamanho somente ao modo correspondente; não combinar
   margem com escala nem registrar parâmetros inativos que criem falsas diferenças.
6. Rejeitar combinações inválidas ou semanticamente repetidas e regenerar
   integralmente o grupo, preservando seus seis perfis e o balanceamento por
   parâmetro. O limite é de 100 tentativas por grupo; se não for possível
   satisfazer as regras, falhar sem relaxá-las
   silenciosamente ou entregar menos configurações.
7. Salvar as 48 configurações completas, o procedimento, sua versão e os
   arquivos de entrada. O executor lê a lista; não sorteia durante a execução.

A quantidade de limiares depende da faixa e do passo. Conferir a
repetibilidade contra essa quantidade e registrar os valores efetivos do
OpenCV. Não interpretar três repetições como a mesma proporção de persistência
em faixas com quantidades diferentes de limiares.

A identidade de configuração inclui os valores efetivos do OpenCV, os
limites da classificação e a caixa canônica. IDs ou nomes de blocos não
tornam duas configurações iguais em distintas; escala 1 e margem 0 são
normalizadas para a caixa original.

Nas 36 exploratórias, vários parâmetros mudam juntos. Elas localizam regiões
promissoras, mas não medem causalmente o efeito isolado de cada parâmetro.
Os rounds seguintes podem incluir comparações controladas para esclarecer
as hipóteses indicadas por esse primeiro conjunto.

## 5. Verificações da implementação

A nova suíte integrada passou em **66 testes sintéticos** e as regressões
passaram em **113 testes**, totalizando **179 testes aprovados**. Foram
revisadas as oito páginas de um PDF com dados sintéticos, cobrindo a
apresentação de 48 configurações. A conferência real `--conferir` passou
para os 178 quadros e as 48 configurações, sem detecção nem criação de
resultados. Essas verificações não representam uma execução do round1 na base.

- Original, escala 1 e margem 0 reproduzem a caixa original.
- Bordas, arredondamentos e parâmetros inválidos têm comportamento definido;
  centro, diâmetro, área bruta e classe são preservados ao adaptar a caixa.
- Planos do round0 continuam carregando sem alterações; o novo plano é validado
  separadamente, com 48 configurações distintas e os 178 quadros acordados.
- O executor usa a avaliação atual, incluindo quadros vazios, erros de classe,
  ausência de casos e agregação por contagens; não usa o avaliador histórico
  de macro-F1 por copiar o executor antigo da limiarização.
- Entradas previstas ausentes ou alteradas interrompem a execução; não há
  exclusões automáticas. Falhas preservam seus registros e resultados parciais.
- Cada execução cria novas pastas e guarda plano, hashes, código, versões,
  parâmetros efetivos, tabelas, imagens, tempos e relatório.
- O PDF suporta 48 configurações e pode ser regenerado sem repetir o detector.

As verificações de código usam dados sintéticos e temporários. Um piloto real,
se necessário, ficará restrito aos casos conhecidos do round0, dependerá da
execução acordada com o pesquisador e será registrado como esforço adicional.
Não é uma exigência de bom F1 antes da rodada.

## 6. Execução e análise

Na raiz do projeto, conferir ambiente, plano, hashes e decodificação das
178 imagens, sem executar detecções nem criar resultados:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round1 --conferir
```

O pesquisador executará o batch com:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round1
```

Também é possível indicar o plano salvo com `--plano`, no lugar de
`--rodada`. A execução lê a lista congelada e repete a conferência antes da
primeira detecção. As saídas ficarão em
`resultados/frame-to-frame/blobs/round1/`, com uma pasta do batch e pastas por
configuração/execução, mantendo o padrão do projeto. Os nomes curtos incluem
modo de caixa e hash da configuração completa. As tabelas preservam as
caixas originais e adaptadas, os centros/diâmetros/áreas brutos e os tempos
do detector, adaptação e conjunto das duas etapas.

O PDF é gerado ao final. Para regenerá-lo sem repetir detecções, informar
a pasta real do batch produzido:

```powershell
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --somente-relatorio ".\resultados\frame-to-frame\blobs\round1\batch__<UTC>"
```

Cada regeneração preserva as versões anteriores. A falha do PDF não apaga
as métricas concluídas. Falhas durante os quadros preservam a execução
incompleta para diagnóstico; uma nova execução usa novas pastas.

Após as 8.544 avaliações, revisar F1 de indivíduos, TP/FP/FN, cobertura de
normais/pequenos, classificação nos pares, aglomerados, diferenças por vídeo
e exemplos visuais. Examinar os 12 controles separadamente das 36 exploratórias.
O round2 será definido pelos resultados; ainda não se escolhem cinco finalistas.

O orçamento posterior e o relatório obrigatório após o round5 permanecem
registrados na [síntese de continuidade](estado_pesquisa.md). A implementação não
introduz segmentação local, treinamento, k-NN, rastreamento ou outro avaliador.
