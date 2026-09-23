# Watershed — plano do round4

21/09/2026. Refinamento aprovado após a [análise do round3](analise_round3_watershed.md).
Plano executável: [round4.json](../scripts/watershed/rodadas/round4.json).
A execução real fica com o pesquisador.

## Objetivo

Comparar **18 configurações nos mesmos 178 quadros**: **3.204 avaliações**,
com **seis controles e 12 configurações novas**. Cada par compara separar
regiões com preservar componentes classificados como aglomerados por área.
Ao concluir a rodada, serão 106 configurações distintas entre round1 e round4.

A líder anterior, r3c18, alcançou F1 de indivíduos 0,478007 com Otsu −5.
Melhorou em sete vídeos e piorou em cinco frente à líder do round2.
As primeiras quatro posições usam −5, mas pequenos continuam pouco cobertos
e existem caixas maiores e menores que as anotadas. O plano refina essa
vizinhança sem presumir melhora ou antecipar finalistas.

## Configurações congeladas

IDs ímpares usam **separar**; pares usam **preservar por área**.

| Par | IDs | Ajuste Otsu | Semente | Área mínima | Fechamento | Papel |
|---|---|---:|---:|---:|---:|---|
| p01 | r4c01/r4c02 | 0 | 0,35 | 120 | 5×5 | Controles r3c01/r3c02 |
| p02 | r4c03/r4c04 | −5 | 0,35 | 120 | 5×5 | Controles r3c17/r3c18 |
| p03 | r4c05/r4c06 | −5 | 0,75 | 120 | 5×5 | Controles r3c21/r3c22 |
| p04 | r4c07/r4c08 | −3 | 0,35 | 120 | 5×5 | Refinar limiar |
| p05 | r4c09/r4c10 | −7 | 0,35 | 120 | 5×5 | Refinar limiar |
| p06 | r4c11/r4c12 | −5 | 0,35 | 132 | 5×5 | Área com a nova máscara |
| p07 | r4c13/r4c14 | −5 | 0,35 | 144 | 5×5 | Área com a nova máscara |
| p08 | r4c15/r4c16 | −5 | 0,50 | 120 | 5×5 | Semente intermediária |
| p09 | r4c17/r4c18 | −5 | 0,35 | 120 | 3×3 | Fechamento menor |

Cada configuração nova tem `contraste_com` apontando para r4c03 ou r4c04,
conforme a política. **Somente um parâmetro muda nesse contraste.**
Os seis controles preservam a referência sem ajuste, a líder e o par
competitivo de semente 0,75. Os pares p01/p02 isolam o efeito de zero para
−5; os pares p02/p03 isolam o efeito de semente 0,35 para 0,75.

### Por que estes valores

- **Otsu −3/−7:** investigam os dois lados de −5. Zero e −10 já foram
  testados; deslocamentos extremos não deram o melhor resultado agregado.
- **Área mínima 132/144:** verificam se um filtro maior pode reduzir falsas
  detecções com a máscara de −5. Seus efeitos com ajuste zero não provam
  o comportamento dessa nova combinação.
- **Semente 0,50:** foi competitiva com ajuste zero e teve a maior cobertura
  de pequenos no round3. Seu cruzamento com −5 ainda não foi executado.
- **Fechamento 3×3:** testa se a máscara ampliada por −5 precisa de menos
  união morfológica. Esse fechamento perdeu com ajuste zero no round2;
  por isso recebe somente um par de exploração controlada.

## Parâmetros e critérios preservados

- Otsu, polaridade clara, imagem original, abertura desligada, fechamento
  retangular com uma iteração, conectividade 8 e área máxima 5.000.
- Pequeno até 120 pixels; aglomerado a partir de 900. Área mínima 132/144
  impede emitir classe 2; com mínimo 120, somente regiões de exatamente
  120 pixels podem recebê-la. A cobertura de pequenos deve ser lida junto
  dos erros de classificação, sem confundir acurácia condicional com recall.
- Caixas continuam envolvendo as regiões segmentadas. Não há margem,
  escala, novo pré-processamento, filtro de forma ou alteração do detector.
- Mesmos 178 quadros de desenvolvimento, com as exclusões 23/900 e 23/1100.
  Nenhum dado reservado para seleção ou vídeos finais é usado na preparação.
- F1 de localização de indivíduos 0+2 como critério principal; aglomerados
  separados. IoU ≥ 0,50, pareamento exclusivo e erros 0/2 registrados à parte.
- Contagens somadas antes do F1; F1 indefinido somente sem TP, FP e FN.
  Empates usam frações exatas, compartilham posição e não recebem peso extra.
- Grade dirigida determinística. Seed 42 é registrada por continuidade;
  não ocorre sorteio. O JSON congelado especifica todas as combinações.

## Execução

Na raiz do projeto:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round4
```

Conferir somente entradas e referências, sem detecção:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round4 --conferir
```

Recuperar apenas o PDF se as métricas já estiverem concluídas:

```powershell
& "C:\Python313\python.exe" ".\scripts\watershed\executar_rodada.py" --rodada round4 --somente-relatorio "CAMINHO_COMPLETO_DO_BATCH"
```

Saída: `resultados/frame-to-frame/watershed/round4/batch__<UTC>/`.
Mantém pastas por configuração/quadro, imagens comparativas, máscaras,
mapas, caixas, avaliações, metadados e tabelas. A pasta de cada configuração
identifica Otsu, semente, política, área, fechamento, hash e execução.
O PDF automático tem cinco páginas; a última apresenta os 12 contrastes novos.
F1 e diferenças de F1 são exibidos com seis casas decimais no round4.

Cada execução cria uma pasta nova. Uma interrupção preserva arquivos parciais;
uma nova execução reinicia em outra pasta, sem retomar automaticamente.
Falha no PDF preserva as métricas e permite usar `--somente-relatorio`.

## Reprodução e conferências

Durante o batch, os **1.068 casos de controle** serão comparados ao round3
em `predicoes.txt`, `deteccoes.csv`, `avaliacao.json` e `diagnostico.json`:
**4.272 comparações de arquivos**. Tempos e títulos de imagens não entram
na comparação de identidade. Divergências interrompem o batch e preservam
os arquivos produzidos para diagnóstico.

O plano vincula as origens por hashes: execução, código e plano do round3,
planos dos rounds anteriores, análise, imagens, anotações e controles.
O gerador reproduz exatamente o JSON existente ou recusa sobrescrevê-lo.
Não é necessário executá-lo antes do batch já preparado.

O detector, escritor de saídas e avaliador permanecem iguais aos do round3.
Somente o comando e o relatório compartilhados foram estendidos nesta etapa.
O arquivo `codigo.zip` conterá 35 fontes; o código anterior fica em
`origens/round3_codigo.zip`. Esses arquivos fazem parte da reprodução.

A conferência sem detecção passou: **4.635 origens íntegras**, 178 imagens
e 1.068 casos de referência disponíveis. A execução real ainda não foi feita.
Conferir entradas e passar testes sintéticos não demonstra que uma hipótese
melhorará os resultados experimentais.

Passaram **67 testes sintéticos**: 56 anteriores e 11 novos. Cobrem plano,
parâmetros, controles, execução, interrupções, preservação de métricas,
integridade e recuperação do PDF. As cinco páginas da prévia fictícia
foram conferidas visualmente. A composição foi comparada com a proposta
aprovada, e os quatro planos somam 106 configurações distintas.

## Arquivos desta etapa

| Função | Arquivos |
|---|---|
| Plano | `scripts/watershed/planejamento_round4.py`, `scripts/watershed/rodadas/round4.json` |
| Execução | `scripts/watershed/execucao_round4.py`, extensão de `scripts/watershed/executar_rodada.py` |
| PDF | `analise/relatorio_round4_watershed.py`, extensão de `analise/relatorio_rodada_watershed.py` |
| Testes | `scripts/testes/test_round4_watershed.py`, ajuste do auxiliar sintético em `test_relatorio_round2_watershed.py` |
| Documentação | Este plano, `estado_pesquisa.md`, `plano_watershed.md` e guias principais |

Após a execução pelo pesquisador, conferir integridade, controles, diferenças
por vídeo, perdas de localização e estabilidade do ranking antes de propor
o round5. A seleção em outras imagens e os testes em vídeo continuam posteriores.
