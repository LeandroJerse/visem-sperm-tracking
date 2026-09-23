# Watershed — proposta do round2

21/09/2026. **Desenho aprovado, implementado e posteriormente executado.**
A [análise do round2](analise_round2_watershed.md) registra a conferência e os resultados.
Baseado exclusivamente na [análise do round1](analise_round1_watershed.md).
Os [32 conjuntos de parâmetros](proposta_round2_watershed.json) estão definidos
no registro original da proposta, preservado sem alterações. O plano executável
está em [round2.json](../scripts/watershed/rodadas/round2.json).

Conferência do desenho: 32 assinaturas distintas, quatro controles idênticos
às referências, 28 combinações novas, 16 pares que diferem somente pela
política e composição dos 178 quadros preservada. Os parâmetros já existentes
passaram pelo parser do watershed; o deslocamento foi implementado e testado
com imagens sintéticas, seguindo os requisitos descritos abaixo.

## Objetivo e desenho

Recomenda-se **32 configurações, incluindo quatro controles**, nos mesmos
178 quadros: 5.696 avaliações previstas e 28 configurações novas.
Se todas forem executadas, serão 76 configurações distintas entre round1 e
round2. Não há alteração das anotações, caixas de referência ou métricas.

A busca passa de dispersa para dirigida. A área mínima apresenta evidência
consistente; sementes, máscara e fechamento precisam de contrastes controlados.
Cada base forma um par de políticas: separar e preservar por área.

| Frente | Configurações | Justificativa |
|---|---:|---|
| Controles r1c11, r1c12, r1c13 e r1c14 | 4 | Preservar as duas políticas e uma alternativa com mais pequenos localizados |
| Áreas 96, 120 e 144 × sementes 0,35 e 0,75 × políticas | 12 | Refinar a região que melhorou nos 12 vídeos e investigar a interação entre área e sementes |
| Deslocamento do Otsu −20, −10, +10 e +20 × políticas | 8 | Investigar caixas pequenas/grandes preservando a adaptação à intensidade de cada imagem |
| Fechamento retangular 3×3 e 7×7 × políticas | 4 | Comparar com 5×5 mantendo máscara inicial, área e sementes constantes |
| Semente 0,15 com área 48; semente 0,50 com área 120 × políticas | 4 | Manter uma hipótese permissiva e interpolar entre as sementes principais |
| **Total** | **32** | **16 pares com referências explícitas** |

Não é um ótimo garantido nem uma busca exaustiva. É uma distribuição do
orçamento coerente com as limitações observadas, que permite explicar os
contrastes e decidir o refinamento seguinte.

## Valores fixos

Polaridade clara; abertura desligada; conectividade 8; área máxima 5.000;
classe pequeno até 120 pixels²; aglomerado a partir de 900 pixels²;
uma iteração de fechamento retangular. Caixas continuam envolvendo os pixels
da região. Nada é expandido artificialmente nesta proposta.

O centro da exploração usa mínimo 120, semente 0,75, fechamento 5×5 e
Otsu sem deslocamento. Mínimo 120 equilibra a investigação dos numerosos FP
abaixo dessa área com a perda crescente de TP observada acima dela.
É uma referência de desenho, não uma configuração já validada.

## Catálogo dos 16 pares

Em cada linha, o primeiro ID separa e o segundo preserva por área.
Área em pixels²; deslocamento em níveis de intensidade de 0 a 255.

| Par | IDs | Frente | Área mínima | Semente | Deslocamento Otsu | Fechamento |
|---|---|---|---:|---:|---:|---|
| p01 | r2c01 / r2c02 | Controles r1c11/r1c12 | 72 | 0,75 | 0 | 5×5 |
| p02 | r2c03 / r2c04 | Controles r1c13/r1c14 | 48 | 0,35 | 0 | 5×5 |
| p03 | r2c05 / r2c06 | Área e semente | 96 | 0,35 | 0 | 5×5 |
| p04 | r2c07 / r2c08 | Área e semente | 96 | 0,75 | 0 | 5×5 |
| p05 | r2c09 / r2c10 | Área e semente | 120 | 0,35 | 0 | 5×5 |
| p06 | r2c11 / r2c12 | Área e semente | 120 | 0,75 | 0 | 5×5 |
| p07 | r2c13 / r2c14 | Área e semente | 144 | 0,35 | 0 | 5×5 |
| p08 | r2c15 / r2c16 | Área e semente | 144 | 0,75 | 0 | 5×5 |
| p09 | r2c17 / r2c18 | Máscara | 120 | 0,75 | −20 | 5×5 |
| p10 | r2c19 / r2c20 | Máscara | 120 | 0,75 | −10 | 5×5 |
| p11 | r2c21 / r2c22 | Máscara | 120 | 0,75 | +10 | 5×5 |
| p12 | r2c23 / r2c24 | Máscara | 120 | 0,75 | +20 | 5×5 |
| p13 | r2c25 / r2c26 | Fechamento | 120 | 0,75 | 0 | 3×3 |
| p14 | r2c27 / r2c28 | Fechamento | 120 | 0,75 | 0 | 7×7 |
| p15 | r2c29 / r2c30 | Semente permissiva | 48 | 0,15 | 0 | 5×5 |
| p16 | r2c31 / r2c32 | Semente intermediária | 120 | 0,50 | 0 | 5×5 |

## Como interpretar as comparações

- Dentro de cada par: somente a política de aglomerados muda.
- p03/p05/p07 e p04/p06/p08: somente a área mínima muda em cada sequência.
- p03/p04, p05/p06 e p07/p08: somente a fração de semente muda, comparando
  sempre a mesma política.
- p09 a p12 contra p06: somente o deslocamento de Otsu muda.
- p13/p14 contra p06: somente o tamanho do fechamento muda.
- p15 contra p02: somente a semente muda de 0,35 para 0,15, com mínimo 48.
- p16 contra p05/p06: semente intermediária 0,50, com mínimo 120.

Não atribuir diferenças entre configurações arbitrárias a um único parâmetro.
A grade pequena de área e semente permite observar se o benefício de um
mínimo depende da semente, além dos contrastes de uma variável por vez.

## Hipótese nova: Otsu com deslocamento

Para cada imagem, calcular o mesmo limiar original de Otsu e então aplicar:

`T_efetivo = min(255, max(0, T_otsu + deslocamento))`

Exemplo: se Otsu retorna 123, os quatro deslocamentos propõem limiares
103, 113, 133 e 143. Em uma imagem cujo Otsu é 194, passam a 174, 184,
204 e 214. O deslocamento é fixo por configuração e não consulta anotações.

Os níveis ±10 fazem a exploração próxima; ±20 verificam uma alteração
moderada mais ampla. Não foram estimados como ótimos. Deslocamento negativo
inclui pixels de menor intensidade; positivo exige pixels mais claros.
Isso pode melhorar contornos, mas também unir objetos, ampliar fundo ou
fragmentar cabeças. Ambos os sentidos precisam ser avaliados.

O método deve ser identificado como variante de Otsu, mesmo que internamente
o limiar calculado seja aplicado por uma operação de limiarização manual.
É uma regra determinística de segmentação clássica, sem treinamento.

### Requisitos aprovados e implementados

1. Manter o detector histórico e os planos round0/round1 reproduzíveis.
   Implementar a variante em uma camada separada, reutilizando o watershed
   atual. Deslocamento zero deve encaminhar ao caminho original.
2. Usar a mesma conversão para cinza. Para deslocamento não zero, calcular
   Otsu nessa imagem original e passar o limiar ajustado ao detector existente,
   preservando morfologia, sementes, classificação e medidas.
3. Registrar por quadro o limiar original, deslocamento e limiar efetivo,
   inclusive sem detecções. Registrar a fração da imagem coberta pela máscara
   final para detectar seleção excessiva de fundo. Novos metadados devem
   ficar separados dos quatro arquivos comparados nos controles.
4. Testar com imagens sintéticas: equivalência em deslocamento zero, limites
   0/255, imagens vazias/uniformes, morfologia, caixas, centroides e ausência
   de alteração da imagem de entrada. Manter os testes anteriores.
5. Preparar executor e PDF para 32 configurações, preservando os leitores
   históricos. Nos quatro controles, conferir os 178 quadros comuns ao round1:
   712 casos e 2.848 comparações de arquivos, além das agregações.
6. Congelar plano, fontes, hashes, dependências e código. Conferir entradas
   sem detecção e deixar a execução real para o pesquisador.

A extensão está em `algoritmos/classicos/variantes_watershed.py`. O detector
histórico não foi alterado. O [guia](../scripts/watershed/README.md) apresenta
o comando do round2, a conferência sem detecção e a recuperação do PDF.
O executor comum e o relatório receberam suporte à nova rodada; o código
exato do round1 continua preservado em seu `codigo.zip`. As duas versões
e seus hashes são arquivados nas origens da nova execução.

O PDF mantém as quatro páginas comparativas e acrescenta uma quinta página
para os contrastes de Otsu, com limiar médio, máscara e diferenças de TP/FP/FN.
A conferência das entradas passou: 178 imagens, 3.209 hashes de origem,
incluindo os 2.848 arquivos de referência dos 712 casos de controle.
Essa conferência não executa o detector nem demonstra ganho de desempenho.

### Arquivos e verificações da preparação

| Função | Arquivos criados ou atualizados |
|---|---|
| Variante de segmentação | `algoritmos/classicos/variantes_watershed.py` |
| Plano aprovado e gerador | `scripts/watershed/rodadas/round2.json`, `planejamento_round2.py` |
| Comando, conferência e saídas | `scripts/watershed/executar_rodada.py`, `execucao_round2.py`, `saidas_round2.py` |
| PDF compartilhado e extensão do round2 | `analise/relatorio_rodada_watershed.py`, `relatorio_round2_watershed.py` |
| Testes novos | `scripts/testes/test_round2_watershed.py`, `test_relatorio_round2_watershed.py` |
| Guias e continuidade | `README.md`, `scripts/README.md`, `scripts/watershed/README.md`, `algoritmos/classicos/README.md`, `analise/README.md`, `analise/plano_watershed.md`, `analise/estado_pesquisa.md` e este documento |

Passaram **45 testes**: os 28 anteriores e 17 novos. Cobrem equivalência em
zero, ajustes positivos e negativos, limites 0/255, imagens uniformes e
inválidas, saídas dos controles, plano reproduzível, interrupções, arquivos
alterados, agregação e recuperação do PDF. Os detectores foram executados
somente em imagens sintéticas. Uma prévia fictícia de cinco páginas foi
renderizada e conferida visualmente; não constitui resultado experimental.

A leitura das 8.544 avaliações do round1 e de seus 24 controles continua
compatível com o relatório atualizado. A conferência do executor histórico
também passou. O novo arquivo `codigo.zip` reunirá 29 fontes; o arquivo
histórico do round1 será preservado em `origens/round1_codigo.zip`.

Reproduzir os testes técnicos, sem executar experimentos da base:

```powershell
& "C:\Python313\python.exe" -m unittest scripts.testes.test_watershed scripts.testes.test_inspecao_watershed scripts.testes.test_rodada_watershed scripts.testes.test_round2_watershed scripts.testes.test_relatorio_round2_watershed -q
```

## Por que não outras mudanças agora

- **Polaridade escura:** até quatro TP e milhares de FP nos testes; retirar
  desta rodada, preservando os resultados como evidência negativa.
- **Limiar manual global:** a faixa de Otsu 67–195 indica grande variação
  entre imagens. Priorizar deslocamentos relativos antes de outra grade global.
- **Aumentar todas as caixas:** coexistem 683 caixas menores que metade e
  531 com pelo menos o dobro da área anotada entre os melhores candidatos
  dos FN com sobreposição. Uma expansão uniforme pode ajudar e prejudicar
  simultaneamente. Primeiro investigar a segmentação.
- **Subir diretamente o mínimo a 192:** atingiria muitas detecções atualmente
  corretas; investigar 96–144 antes de avançar.
- **Alterar limites de classe:** apenas quatro FN da líder têm caixa válida
  emitida como aglomerado. O problema dominante precede a classificação.
  Alterar só 0/2 não recupera localização sob a métrica agrupada.
- **Abertura e novos pré-processamentos:** a abertura testada piorou um
  contraste controlado. Não acrescentar CLAHE, classificadores ou filtros
  de forma junto com esta hipótese, para manter a investigação delimitada.

Mínimo 144 impede emitir classe 2 pela regra atual. Isso será registrado,
assim como os acertos de localização de pequenos classificados como 0.
A frente de mínimo 48 permanece para não abandonar a investigação de pequenos.

## Protocolo e decisão depois da execução

Mesmos 178 quadros e duas exclusões do vídeo 23, mesmos grupos 0+2 e 1,
IoU 0,50, pares exclusivos e contagens somadas antes de F1. Manter empates
exatos, sem peso novo para classes ou alteração do ranking. Seed 42 permanece
registrada; a grade é determinística e não usa sorteio.

Após conferir a execução, examinar F1, TP/FP/FN, cobertura de pequenos,
classificação condicional, resultados por vídeo e os contrastes definidos.
Separar ganho de precisão por rejeição de caixas de ganho de localização por
melhora da máscara. Usar retirada de um vídeo por vez como diagnóstico de
sensibilidade, sem tratá-la como teste independente de generalização.

O ranking de desenvolvimento não escolhe finalistas. Depois das rodadas,
mantém-se seleção nos 60 quadros reservados, revisão das cinco configurações,
vídeos de seleção e avaliação final com escolhas congeladas. Nenhum desses
dados reservados foi consultado para esta proposta.
