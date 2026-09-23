# Diagnóstico do round0 de watershed

## Estado e integridade

Inspeção concluída pelo pesquisador no batch
`resultados/frame-to-frame/watershed/round0/batch__20260921T135941123246Z`.
As oito configurações processaram os mesmos seis quadros de desenvolvimento:
**48 avaliações completas**, sem nova execução do detector nesta auditoria.

Foram conferidos 551 hashes de saídas, 16 de origens, o PDF de duas páginas
e seu vínculo com o manifesto. As duas páginas foram renderizadas e revistas.
As comparações visuais de w04 nos quadros 12/200, 19/0 e 21/0 foram examinadas.

Durante a auditoria, o pesquisador removeu `codigo.zip`. Os 21 arquivos de
código atuais ainda correspondiam aos hashes arquivados. Após autorização,
o ZIP foi restaurado **com SHA-256 idêntico ao original**:
`7ab372bae14adec08402fe7881491b632e7408d2b6728fcdd3014960aba2543b`.
A conferência completa foi repetida com sucesso. Manifesto, métricas, mídias
e PDF permaneceram inalterados.

## Compatibilidade das caixas confirmada

A auditoria dos mapas salvos abrangeu 2.069 regiões candidatas, 1.659 detecções
emitidas e 1.768 componentes, somados entre as 48 avaliações. As repetições
de uma mesma imagem/configuração não representam amostras independentes.

- Cada caixa corresponde exatamente aos extremos dos pixels da região.
- Áreas, centroides e intensidades médias correspondem aos pixels registrados.
- Classes e exclusões seguem os limites congelados da configuração.
- As coordenadas do TXT normalizado correspondem às caixas do CSV.
- Todos os pixels da máscara pertencem a uma região, sem vazamento para o fundo.
- Componentes preservados têm uma região, sem emitir pai e filhos juntos.
- O pareamento recalculado sobre as caixas salvas reproduziu as 48 avaliações.

Portanto, **o formato é compatível e não foi encontrado erro de exportação**.
Uma caixa correta para a região segmentada ainda pode representar apenas uma
parte do espermatozoide ou juntar objetos: isso é erro de detecção, medido
contra a anotação preservada.

## Resultados iniciais

A amostra contém 160 ocorrências normais, sete pequenas e cinco aglomerados.
Todas as configurações usaram Otsu e fechamento retangular 5×5, com área
aceita entre 3 e 5.000 pixels, pequeno até 120 e aglomerado desde 900 pixels.

| Configuração | Polaridade | Semente | Política | TP indivíduos | FP indivíduos | FN indivíduos | F1 indivíduos | Aglomerados localizados |
|---|---|---:|---|---:|---:|---:|---:|---:|
| w01 | claro | 0,50 | separar | 81 | 330 | 86 | 0,280277 | 1/5 |
| w02 | claro | 0,50 | preservar | 80 | 313 | 87 | 0,285714 | 4/5 |
| w03 | claro | 0,75 | separar | 83 | 307 | 84 | 0,298025 | 3/5 |
| w04 | claro | 0,75 | preservar | 83 | 304 | 84 | 0,299639 | 4/5 |
| w05–w08 | escuro | ambas | ambas | 0 | 11 | 167 | 0 | 0/5 |

O maior F1 observado foi w04, com precisão de 21,45% e recall de 49,70%.
Seus 83 acertos são normais; quatro foram classificados como pequenos,
sem perder o acerto de localização pelo critério acordado. Nenhum dos sete
pequenos anotados foi localizado por qualquer configuração.

Não há escolha de finalistas nesta inspeção. A amostra foi intencionalmente
pequena e variada; esses números não estimam o desempenho geral nem justificam
comparação direta com os F1 de blobs nos 178 quadros ou nos vídeos completos.

## O que explica o desempenho

### Excesso de regiões pequenas

Em w04, **147 dos 304 falsos positivos de indivíduos** têm área menor que
48 pixels. Nenhum dos 83 verdadeiros positivos tem área abaixo de 95 pixels.
Isso fundamenta explorar filtros de área e abertura no round1. Não estabelece
95 como limite ideal: seria ajustar excessivamente a estes seis casos.

Elevar o mínimo também pode eliminar pequenos reais em outras imagens.
Devem permanecer configurações com filtro permissivo e acompanhamento da
cobertura por classe. A falta de pequenos não será corrigida apenas trocando
os limites entre classe 0 e 2, pois o F1 atual já agrupa ambas.

### Máscara e tamanho das regiões

Nas 84 perdas de indivíduos de w04, o maior IoU com qualquer região candidata
(incluindo rejeitadas) foi inferior a 0,50 em todos os casos. Em seis deles
não houve sequer sobreposição com uma caixa candidata; nos outros 78 houve
sobreposição insuficiente.

Entre esses 78 casos, a caixa de maior IoU tinha área:

- menor que metade da anotação em 32 casos;
- entre metade e o tamanho da anotação em seis;
- igual ou maior que a anotação em quarenta.

O centro da caixa candidata estava dentro da anotação em 66 desses casos.
Esses pares são diagnósticos individuais, não um novo pareamento exclusivo.
Os números apontam tanto regiões incompletas quanto regiões grandes ou
desalinhadas. **Aumentar todas as caixas não é uma correção universal.**
Primeiro convém explorar limiar, morfologia e sementes, preservando a caixa
derivada dos pixels como referência.

Para os sete pequenos anotados, seis não têm sobreposição com candidatos
da polaridade clara; o sétimo tem IoU de apenas 0,005 com uma região rejeitada
por área. Nesta amostra, a geração da máscara é uma limitação anterior à
classificação ou ao ajuste fino das caixas.

### Polaridade escura e fundo

Otsu escuro, seguido do fechamento empregado, selecionou entre **96,49% e
99,53% da imagem**. Predominaram regiões enormes, muitas excluídas pelo máximo
de área. Já a polaridade clara selecionou entre 0,92% e 6,86% dos pixels.
Isso explica o insucesso da combinação escura atual. Não prova que limiares
manuais mais baixos para regiões escuras sejam inúteis; merecem uma parcela
menor e identificada da exploração inicial, especialmente pelos pequenos.

### Preservação de aglomerados e sementes

Com semente 0,75, preservar aglomerados manteve os 83 acertos de indivíduos,
reduziu FP de 307 para 304 e elevou aglomerados localizados de três para quatro.
Com semente 0,50, a preservação reduziu dezessete FP, perdeu um acerto de
indivíduo e elevou aglomerados localizados de um para quatro.

Essa é evidência inicial a favor de manter a comparação das duas políticas,
não de eliminar a separação. Há apenas cinco aglomerados anotados, quatro
deles no mesmo quadro do vídeo 19.

Também não se deve interpretar uma fração maior como garantia de mais sementes:
na polaridade clara, o total caiu de 497 para 479 ao passar de 0,50 para 0,75.
Restringir os núcleos pode separar partes conectadas, mas também pode eliminar
núcleos secundários. O efeito depende da geometria da máscara.

## Direção proposta para round1

O round0 cumpriu a validação técnica. O próximo passo é a busca ampla nos
**mesmos 178 quadros de desenvolvimento**, preservando métricas e partições.
Propõe-se um orçamento inicial de **48 configurações**:

- quatro referências claras do round0, para conferir reprodução e servir de controle;
- 36 configurações claras: dezoito bases de parâmetros, cada uma com as duas políticas;
- oito configurações escuras: quatro bases exploratórias, também em pares de políticas.

As frentes são limiar manual/Otsu, abertura e fechamento, fração das sementes,
área mínima e limite de aglomerado. Limite pequeno permanece relatado à parte:
alterá-lo entre 0 e 2 não melhora diretamente o F1 de localização acordado.
A busca deve conter configurações permissivas para investigar os pequenos,
além das que filtram ruído mais agressivamente.

Esta proposta foi aprovada e concretizada no
[plano do round1](plano_round1_watershed.md), com 48 configurações congeladas
e executor preparado para o pesquisador. A busca
será refinada pelos resultados nos 178 quadros, mantendo controles e registros,
antes de seleção em outras imagens e testes nos vídeos. Nenhum teste adicional
ou ajuste de detector foi executado nesta análise.

## Fontes

- [Estatísticas e auditoria das regiões](estatisticas_round0_watershed.json).
- [Plano e regras do watershed](plano_watershed.md).
- [Resumo da execução](../resultados/frame-to-frame/watershed/round0/batch__20260921T135941123246Z/resumo_configuracoes.csv).
- [PDF original](../resultados/frame-to-frame/watershed/round0/batch__20260921T135941123246Z/relatorios/20260921T135955589978Z/relatorio.pdf).
- [Guia de execução](../scripts/watershed/README.md).
