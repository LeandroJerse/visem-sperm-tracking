# Watershed — análise do round1

21/09/2026. Análise dos resultados salvos, sem executar novamente o detector.
Batch: `resultados/frame-to-frame/watershed/round1/batch__20260921T143759308685Z`.

**Conclusão:** a rodada terminou íntegra. Aumentar a área mínima melhorou
consistentemente a precisão, com pequena perda de acertos. Entretanto, a
localização ainda é limitada pelo tamanho e formato das regiões segmentadas.
O próximo round deve refinar área e sementes e investigar a máscara, mantendo
as duas políticas de aglomerados. A [proposta do round2](proposta_round2_watershed.md)
detalha 32 configurações, ainda sem implementação ou execução.

## 1. Conferência da execução

- 48 configurações × 178 quadros = **8.544 avaliações concluídas**.
- 94.187 hashes de saídas e 457 de origens conferidos, sem divergências.
- Plano, parâmetros, 24 arquivos de código arquivados, ZIP e cópias de origem
  íntegros. O código usado na análise corresponde ao arquivado.
- Resumos completos: 48 configurações, 576 linhas por vídeo e 8.544 por quadro.
  Ranking recalculado a partir das contagens, preservando empates exatos.
- As 8.544 avaliações JSON reconciliam com os resumos. Cada quadro tem os
  onze arquivos previstos, incluindo caixas, avaliação, imagens e mapas.
- Os 24 casos de controle reproduzem o round0, incluindo 96 arquivos
  de previsões, detecções, avaliações e diagnósticos idênticos.
- As avaliações dos 178 quadros de r1c11 foram recalculadas a partir das
  caixas salvas, com pareamento exclusivo, e coincidiram integralmente.
- Em cinco quadros de r1c11 (11/0, 19/0, 23/0, 30/0 e 60/0), foram
  conferidas 333 regiões e 166 detecções contra os mapas: áreas, caixas,
  centroides e cobertura da máscara corretos.
- PDF de quatro páginas com hashes válidos e páginas revisadas visualmente.
  Comparações de 19/0, 30/0 e 60/0 também inspecionadas.

A execução registrada durou aproximadamente 36 minutos e 50 segundos,
antes da geração do PDF. Esse tempo inclui gravações e avaliações, além
da detecção. Nenhum resultado original foi alterado nesta análise.

## 2. Resultados e comparação justa

Os valores abaixo vêm dos **mesmos 178 quadros**. Não se compara o maior F1
do round1 diretamente com o F1 do round0 de apenas seis imagens.

| Configuração | Área mínima | Semente | Política | F1 indivíduos | Precisão | Sensibilidade | TP | FP | FN |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| r1c03 — controle | 3 | 0,75 | separar | 0,270743 | 0,1819 | 0,5292 | 1.904 | 8.563 | 1.694 |
| r1c02 — maior F1 entre controles | 3 | 0,50 | preservar | 0,275414 | 0,1876 | 0,5181 | 1.864 | 8.074 | 1.734 |
| r1c09 | 48 | 0,75 | separar | 0,405250 | 0,3289 | 0,5278 | 1.899 | 3.875 | 1.699 |
| **r1c11** | **72** | **0,75** | **separar** | **0,429887** | **0,3638** | **0,5253** | **1.890** | **3.305** | **1.708** |
| r1c12 | 72 | 0,75 | preservar | 0,429442 | 0,3663 | 0,5189 | 1.867 | 3.230 | 1.731 |
| r1c13 | 48 | 0,35 | separar | 0,412326 | 0,3405 | 0,5225 | 1.880 | 3.641 | 1.718 |
| r1c14 | 48 | 0,35 | preservar | 0,418500 | 0,3522 | 0,5156 | 1.855 | 3.412 | 1.743 |

No contraste r1c03 → r1c11, somente a área mínima muda de 3 para 72:
**5.258 FP a menos, 14 TP a menos e ganho de 0,159144 em F1**.
O F1 melhora nos **12 vídeos**, inclusive ao comparar mínimo 48 com 72.
É a evidência mais consistente desta rodada para orientar o refinamento.

FP significa caixa sem correspondência válida nas anotações. Não significa
necessariamente que todo objeto marcado seja ruído: uma cabeça localizada
com caixa inadequada também pode produzir FP e FN simultaneamente.

## 3. Área mínima: onde refinar e onde ter cuidado

Nos indivíduos emitidos por r1c11, a mediana da área é 247 pixels² entre
os TP e 181 entre os FP. Existe sobreposição considerável entre os grupos;
área sozinha não separa todos os objetos corretos dos incorretos.

| Área segmentada, intervalo [mínimo, máximo) | TP | FP | TP de pequenos anotados |
|---|---:|---:|---:|
| 72–96 | 19 | 471 | 1 |
| 96–120 | 45 | 413 | 0 |
| 120–144 | 104 | 340 | 0 |
| 144–192 | 286 | 527 | 0 |
| 192–384 | 1.086 | 947 | 2 |
| 384–900 | 350 | 607 | 3 |

Isso sustenta testar **96, 120 e 144**, mantendo referências com 48 e 72.
Não sustenta escolher imediatamente o maior mínimo possível: passar de
144 para 192 atingiria mais 286 detecções hoje pareadas. Os intervalos são
um diagnóstico dos pares atuais, não uma simulação do F1 de configurações
novas. O pareamento deve ser refeito durante sua avaliação.

## 4. O principal problema restante está nas regiões e caixas

Para cada indivíduo perdido por r1c11, foram examinados todos os candidatos
salvos, inclusive os rejeitados por área. O diagnóstico não usa associação
exclusiva: serve para localizar a limitação, não para contabilizar novos TP.

| Situação dos 1.708 indivíduos perdidos | Quantidade |
|---|---:|
| Há sobreposição, mas nenhum candidato alcança IoU 0,50 | 1.612 |
| Nenhum candidato sobrepõe a anotação | 69 |
| Há caixa compatível, mas rejeitada por área | 14 |
| Há candidato de indivíduo compatível, mas sem par exclusivo disponível | 9 |
| Há caixa compatível emitida como aglomerado | 4 |

Entre os **1.639 FN com alguma sobreposição**, tomando o candidato de maior
IoU de cada anotação:

- 683 caixas têm área menor que metade da caixa anotada;
- 200 têm área entre metade e o total anotado;
- 225 têm área entre uma e duas vezes a anotada;
- 531 têm área de pelo menos o dobro;
- 1.373 centros de caixa estão dentro da caixa anotada;
- 1.180 melhores sobreposições ficam entre IoU 0,25 e 0,50.

Também há **1.092 dos 3.305 FP** com centro dentro de um indivíduo anotado,
mas IoU inferior a 0,50 com todos os indivíduos. Portanto, parte importante
do problema é delimitar o objeto, além de encontrar sua região aproximada.

O comportamento difere entre vídeos: no 60, 165 dos melhores candidatos
com sobreposição têm menos da metade da área da anotação; no 11, 128 têm
pelo menos o dobro. Isso desaconselha aumentar todas as caixas como primeira
correção. A representação funciona tecnicamente; a segmentação gera regiões
pequenas, grandes ou desalinhadas conforme a imagem. O round2 investigará
primeiro máscara, sementes e fechamento, mantendo caixas derivadas dos pixels.

## 5. Pequenos e classificação

Há 3.464 anotações normais, 134 pequenas e 109 de aglomerados nos 178 quadros.
Essas são ocorrências por quadro, não indivíduos únicos acompanhados no tempo.

- r1c11 localiza **1.884/3.464 normais** e apenas **6/134 pequenos**.
- r1c13/r1c14 localizam 12 pequenos. Os controles r1c01/r1c02 chegam a 15,
  com muito mais FP. Nenhuma configuração resolveu essa dificuldade.
- Dos 128 pequenos perdidos por r1c11, 63 não têm candidato sobreposto,
  63 têm sobreposição insuficiente e apenas dois têm caixa válida rejeitada
  por área. Diminuir somente o filtro mínimo não resolve a maioria.
- A classificação 0/2 tem 71 erros entre os 1.890 indivíduos localizados
  por r1c11: acurácia condicional de 96,24%. Isso não inclui os perdidos e FP.

Um mínimo de área de 144, acima do limite pequeno de 120, impede emitir o
rótulo 2 nessa regra por área. Ainda pode localizar uma anotação de classe 2
como classe 0, o que é TP de localização e erro de classificação conforme
o protocolo. Esse efeito precisa aparecer na análise, sem mudar a regra
de pontuação para favorecer uma configuração depois de ver seus resultados.

O round2 mantém os limites de classificação e uma frente mais permissiva
para investigar pequenos. k-NN permanece reservado ao modelo híbrido.

## 6. Sementes, políticas e morfologia

Com mínimo 48, trocar semente 0,75 por 0,35 melhora o F1 de 0,405250 para
0,412326 ao separar e de 0,404572 para 0,418500 ao preservar. O ganho ocorre
em sete e oito vídeos, respectivamente; é menos uniforme que o ganho da área.
Vale cruzar as duas sementes com os novos mínimos, sem assumir superioridade
universal da fração menor. A fração 0,90 não trouxe vantagem clara nessa base.

r1c11 e r1c12 diferem somente na política de aglomerados. Preservar perde
23 acertos de indivíduos, remove 75 FP e encontra sete aglomerados a mais
(36 em vez de 29). A diferença de F1 de indivíduos é apenas **0,000445**.
Preservar melhora o F1 em seis vídeos, empata em cinco e piora no vídeo 35.

Retirando um vídeo por vez da agregação, a liderança permanece com r1c11
em onze casos e passa para r1c12 quando se retira o vídeo 35. É uma análise
de sensibilidade descritiva, não validação cruzada nem prova estatística
de superioridade. As duas políticas devem continuar representadas.

O fechamento retangular 5×5 foi uma boa referência nesta busca. A abertura
elíptica 3×3, mantendo Otsu, mínimo 24, semente 0,75 e fechamento retangular
5×5, reduziu F1 de 0,360042 (r1c07) para 0,337173 (r1c27).
A proposta mantém abertura desligada e testa fechamento 3×3 e 7×7, com os
demais parâmetros fixos. Esses resultados locais não provam que outras
combinações de morfologia sejam inúteis.

## 7. Limiar e variação entre vídeos

Otsu escolheu limiares entre **67 e 195**, com mediana 123 e quartis 112 e 146,
calculados uma vez por quadro. As medianas variam, por exemplo, de 93 no
vídeo 23 a 194 no 35. Um limiar manual global pode servir para uma imagem
e segmentar principalmente fundo em outra.

As configurações manuais do round1 também alteraram outros parâmetros,
portanto seu resultado não isola o efeito do limiar. As oito configurações
escuras tiveram no máximo quatro TP de indivíduos e F1 inferior a 0,0006:
não justificam receber novas tentativas neste próximo orçamento.

Recomenda-se uma hipótese nova e identificada: **Otsu com deslocamento fixo**
de −20, −10, +10 ou +20 níveis de intensidade, mantendo a adaptação de Otsu
à imagem. Um deslocamento negativo inclui pixels menos claros e um positivo
restringe a máscara aos mais claros. O efeito nas regiões finais depende
também da morfologia e das sementes. É uma hipótese ainda não testada.

| Vídeo | F1 r1c11 | TP | FP | FN |
|---|---:|---:|---:|---:|
| 11 | 0,4463 | 299 | 488 | 254 |
| 12 | 0,3609 | 131 | 213 | 251 |
| 15 | 0,4046 | 123 | 236 | 126 |
| 19 | 0,1540 | 78 | 657 | 200 |
| 21 | 0,6319 | 224 | 155 | 106 |
| 22 | 0,5451 | 142 | 212 | 25 |
| 23 | 0,1108 | 20 | 308 | 13 |
| 30 | 0,7381 | 155 | 97 | 13 |
| 35 | 0,5254 | 300 | 369 | 173 |
| 36 | 0,5759 | 366 | 231 | 308 |
| 47 | 0,2509 | 34 | 154 | 49 |
| 60 | 0,0876 | 18 | 185 | 190 |

O desempenho não é uniforme. Não serão criados parâmetros específicos para
cada vídeo: todas as configurações propostas continuam avaliadas nos mesmos
178 quadros. O deslocamento proposto é constante por configuração; somente
o limiar original de Otsu depende da imagem, sem consultar anotações.

## 8. Limites da conclusão e sequência

São dados de desenvolvimento reutilizados para ajustar parâmetros. Ganhos
nessa partição orientam a busca, mas não comprovam generalização. As contagens
são somadas antes do F1; vídeos com mais objetos e detecções contribuem mais
para esse agregado. Resultados por vídeo e sensibilidade da ordem esclarecem
essa composição, sem substituir o critério principal acordado.

Não foram aplicados testes tratando os 178 quadros como observações
independentes. Não se alteraram métricas, IoU, classes, partições ou anotações.
O histórico de exposição a dados em versões anteriores continua registrado.

Próxima etapa proposta: aprovar o desenho do round2, implementar e testar
o deslocamento opcional de Otsu, conferir os controles e congelar a rodada
para execução pelo pesquisador. A sequência de rodadas, seleção em outras
imagens e vídeos permanece a mesma.

## Registros

- [Estatísticas, contrastes e diagnóstico](estatisticas_round1_watershed.json).
- [Plano explicado do round1](plano_round1_watershed.md).
- [PDF da execução](../resultados/frame-to-frame/watershed/round1/batch__20260921T143759308685Z/relatorios/20260921T151450425237Z/relatorio.pdf).
- [Proposta do round2](proposta_round2_watershed.md) e
  [parâmetros completos propostos](proposta_round2_watershed.json).
