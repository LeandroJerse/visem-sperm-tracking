# Blobs — desenho do round2

20/09/2026. Registro do desenho anterior à execução. O round2 foi executado;
veja a [análise dos resultados](analise_round2_blobs.md) e a
[proposta do round3](proposta_round3_blobs.md). As justificativas abaixo
preservam as hipóteses formuladas antes de observar os resultados.

## Por que continuar sem reiniciar

O round1 respondeu à exploração inicial do SimpleBlobDetector e demonstrou
que as caixas e a geração de candidatos precisam ser estudadas separadamente.
Não foi identificado erro que invalide suas métricas. CLAHE, LoG e DoG são
extensões motivadas por esses resultados, portanto entram no round2 com
identificação própria. Não apagar nem renumerar o histórico.

Mantêm-se os mesmos 178 quadros de desenvolvimento, anotações originais,
IoU mínimo 0,50 e correspondência exclusiva. Classes 0/2 formam indivíduos;
trocas entre elas são erros de classificação separados. Aglomerados continuam
como grupo próprio. F1 agrega TP/FP/FN; não é média dos F1 dos quadros.
Nenhuma imagem de seleção ou vídeo final participa deste ajuste.

O orçamento permanece de cinco rodadas: 48/32/24/18/14 configurações,
incluindo repetições, e até 122 distintas. O round2 acrescenta 28 às 48 do
round1, totalizando 76 distintas. LoG/DoG receberam menos tentativas até aqui:
não apresentar os três detectores como buscas de igual esforço. O eventual
relatório após o round5 deverá registrar essa diferença e suas limitações.

## Composição: 32 configurações × 178 quadros

| Frente | Quantidade | Comparação |
|---|---:|---|
| Repetições | 4 | r1c29, r1c23, r1c26 e r1c43, com os mesmos parâmetros e caixas |
| Refinamentos do SimpleBlobDetector | 12 | Uma alteração por vez em relação à referência |
| CLAHE antes do SimpleBlobDetector | 8 | Cada referência com limite 1 ou 2, grade 8×8 |
| LoG sem CLAHE | 4 | Dois limiares de resposta × duas caixas |
| DoG sem CLAHE | 4 | Dois limiares de resposta × duas caixas |

O [plano executável](../scripts/blobs/rodadas/round2.json) contém todos os
valores, a origem de cada variante, a ordem e os hashes das entradas.
Não há sorteios nem ajustes durante a execução. Seed 42 é registrada por
continuidade; aqui a construção é determinística a partir do plano anterior.

### Referências e refinamentos

R1c29 obteve o maior F1 de indivíduos (0,551828), mas localizou só 2/134
pequenos. R1c23 preserva uma alternativa clara com caixa em escala; r1c26
teve vantagens em alguns vídeos; r1c43 representa a melhor exploração escura
e localizou 28/134 pequenos, embora com F1 geral baixo. A inclusão desta
última é uma hipótese de recuperação, não uma recomendação de uso final.

Dez variações partem de r1c29, cada uma alterando somente um parâmetro:

- Margem de 2, 3, 5 ou 6 pixels, comparada à referência de 4. Havia caixas
  grandes e pequenas demais: aumentar todas indiscriminadamente não resolve.
- Área mínima interna de 8, 16 ou 48, comparada a 32. Testa a troca entre
  recuperar candidatos e excluir falsos positivos.
- Inércia mínima de 0,2 ou filtro desligado, comparada a 0,4.
- Distância mínima de 6 pixels, comparada a 12.

Duas variações partem de r1c43: área mínima 8 ou inércia mínima 0,2,
alteradas separadamente. Não há fusão das saídas claras e escuras.

Os limites de classificação permanecem os da referência. Mudar apenas a
classe entre 0 e 2 não recupera candidatos ausentes nem melhora o F1 agrupado.
Área interna do filtro, área circular estimada e área da caixa são medidas
diferentes; seus números não podem ser tratados como equivalentes.

### CLAHE como teste pareado de contraste

CLAHE redistribui intensidades em regiões locais com limitação de contraste.
A implementação usa cinza uint8, `clipLimit` 1 ou 2 e `tileGridSize=(8,8)`.
Essa grade significa oito regiões em cada direção, não blocos de oito pixels.
O método pode favorecer detalhes discretos e também aumentar respostas de
ruído. [Documentação do OpenCV](https://docs.opencv.org/4.13.0/d5/daf/tutorial_py_histogram_equalization.html).

Cada configuração mantém detector, filtros, classificação e caixa de uma
referência repetida na mesma rodada. A diferença mede o efeito do CLAHE
**com aqueles parâmetros fixos**, sem provar seu melhor desempenho possível.
Não combinar CLAHE com LoG/DoG nesta primeira sondagem evita acrescentar
mais uma variável às novas famílias e cabe no orçamento disponível.

### LoG e DoG como detectores identificados

LoG procura respostas do Laplaciano de Gaussiana em múltiplas escalas;
DoG usa diferenças de Gaussianas. Eles não reutilizam limiares 0–255,
repetibilidade e filtros de contorno do SimpleBlobDetector.
[API e representação das saídas](https://scikit-image.org/docs/stable/api/skimage.feature.html#skimage.feature.blob_log).

Para cada um, a primeira sondagem usa:

| Parâmetro | Valores | Motivo |
|---|---|---|
| Polaridade | Clara | Melhor frente geral do round1; não esgota a alternativa escura |
| Sigma | 2 a 12 pixels | Faixa inicial de tamanhos, incluindo candidatos pequenos |
| Amostragem LoG | 10 escalas lineares | Cobertura limitada e explícita da faixa |
| Amostragem DoG | Razão 1,6 | Sequência geométrica de escalas |
| Limiar absoluto da resposta | 0,02 ou 0,05 | Contrastar maior sensibilidade e maior rejeição |
| Sobreposição admitida | 0,5 | Regra fixa de supressão de candidatos sobrepostos |
| Caixa | Original ou margem de 2 pixels | Verificar geometria sem usar margens grandes de outro detector |

A imagem é convertida para float64 no intervalo [0,1]; polaridade escura,
suportada pelo código mas não sondada aqui, inverte as intensidades. Não há
reescalonamento de cada imagem por seu mínimo/máximo. O limiar de resposta
não é confiança de que o candidato seja um espermatozoide; seus valores
também não significam sensibilidade idêntica entre LoG e DoG.

As bibliotecas devolvem coordenadas e sigma. Em 2D, usa-se raio estimado
√2×sigma e diâmetro 2√2×sigma; sigma bruto e origem são preservados na tabela.
A caixa usa floor/ceil e recorte na borda. Margens alteram a caixa, sem alterar
sigma, diâmetro, classe ou área circular. A área permanece uma estimativa,
nunca a área de uma máscara segmentada. A sequência de escalas DoG pode
terminar em um valor diferente do máximo solicitado; registrar os parâmetros
e o sigma devolvido preserva o que o backend efetivamente produziu.

Os limites iniciais de classificação correspondem a diâmetro ≤8 para pequeno
e ≥24 para aglomerado; o intervalo intermediário é normal. São hipóteses
geométricas, não definições biológicas. Não se presumem calibrados porque
foram usados em outra família. O foco primário permanece localizar indivíduos.

## Reproduzir e inspecionar

Na raiz do projeto, usando o Python dos experimentos:

```powershell
& "C:\Python313\python.exe" -m pip install -r ".\algoritmos\classicos\requirements-blobs.txt" -r ".\analise\requirements.txt" -r ".\analise\requirements-relatorio.txt"
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round2 --conferir
& "C:\Python313\python.exe" ".\scripts\blobs\executar_rodada.py" --rodada round2
```

A instalação serve a um ambiente novo, com Python 3.11 ou posterior
(requisito do scikit-image 0.26.0). A conferência verifica dependências,
hashes e decodificação das 178 imagens, sem detectar nem criar resultados.
O último comando realiza 5.696 avaliações e cabe ao pesquisador executá-lo.

As saídas ficam em `resultados/frame-to-frame/blobs/round2/`, preservando
o padrão de batch e pastas por configuração/execução. Os nomes identificam
método, processamento, caixa e hash. Cada configuração guarda os parâmetros
completos e os efetivos do backend. O batch arquiva código e planos de origem.

As comparações usam a imagem original como fundo. Configurações com CLAHE
também salvam `preprocessamento.png` para visualizar a entrada processada.
Os tempos de pré-processamento, detector e adaptação são separados; a soma
é o tempo do pipeline. Avaliação, gravação e PDF ficam fora dessa medição.

O PDF adota gráficos ordenados, precisão/recall, cobertura de cada classe,
classificação condicional, resultados por vídeo e comparações controladas.
Mantém as métricas vigentes, sem restaurar o macro-F1 histórico. Cada nova
geração preserva as anteriores e não repete detecções.

## Decisão após a execução

Conferir a integridade, comparar cada hipótese com sua referência e revisar
melhoria de F1 junto com cobertura de pequenos, FP e diferenças por vídeo.
Não declarar CLAHE, LoG ou DoG superiores apenas por uma imagem ou pela
maior quantidade de detecções. Novas combinações dependerão dos resultados
para preparar o round3 de 24 configurações; não foram escolhidas agora.

Após os cinco rounds, produzir o documento explicativo de blobs solicitado,
antes da seleção em outras imagens e dos vídeos. k-NN permanece na etapa híbrida.

## Implementação e conferências desta preparação

| Arquivos | Alteração |
|---|---|
| `algoritmos/classicos/variantes_blobs.py` | Pré-processamento e detectores em escala |
| `algoritmos/classicos/comum.py` | Sigma e origem, mantendo os registros anteriores de SimpleBlobDetector |
| `algoritmos/classicos/requirements-blobs.txt` | Referência scikit-image 0.26.0 |
| `scripts/blobs/planejamento.py`, `planejamento_round2.py`, `rodadas/round2.json` | Contrato v2, desenho, controles e plano congelado |
| `scripts/blobs/executar_rodada.py` | Encaminhamento dos métodos, pré-processamento, tempos e exportação |
| `analise/relatorio_rodada_blobs.py` | PDF compacto, retrocompatível e com variantes identificadas |
| `scripts/testes/test_variantes_blobs.py`, `test_planejamento_round2_blobs.py`, `test_executar_variantes_blobs.py`, `test_relatorio_rodada_blobs.py` | Casos sintéticos e conferências de regressão |
| READMEs, plano geral, análise do round1 e estado da pesquisa | Comandos, justificativas e continuidade |

Passaram **230 testes distintos** nas suítes afetadas e suas regressões,
incluindo imagens sintéticas, exportação, inspeção, diagnóstico e avaliação.
O preflight real conferiu 32 configurações e 178 imagens sem executar detecções
ou criar a pasta round2. Isso valida funcionamento, não eficácia na base.

O PDF real do round1 foi regenerado somente a partir dos dados salvos,
com quatro páginas renderizadas e revisadas. Versão nova:
`batch__20260920T193937586038Z/relatorios/20260920T202745884789Z/relatorio.pdf`.
O PDF antigo e os arquivos de métricas foram preservados.

Hashes SHA256 conferidos:

- Round1 preservado: `59eba7c3ca133b45c5b581860677add18675a2458fbc65d28d267cf5883b2b69`.
- Round2: `29a9ae0de042b1da2a5b5563d9834565e5b8a8069a53e302793389b7435755da`.

O plano round2 foi regenerado em memória com resultado idêntico. Nenhum
parâmetro foi escolhido usando detecções novas durante esta preparação.
