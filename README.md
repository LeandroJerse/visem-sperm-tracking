# TCC — reinício acompanhado

Branch: `codex/avaliacao-deteccao`.

Esta versão foi reiniciada com as bases existentes, em `bases_de_dados/`.
Consulte `bases_de_dados/LEIA_PRIMEIRO.md` para localizar vídeos, imagens e
anotações. Os arquivos pesados permanecem locais; não estão armazenados no Git.

O primeiro método está escrito em `algoritmos/classicos/limiarizacao.py`:
limiarização manual ou Otsu, abertura, fechamento e componentes conectados.
O pesquisador realizou uma primeira inspeção individual do quadro 0 do vídeo 11.
Essa execução não constitui validação experimental do método.
Blobs e Watershed serão implementados em etapas posteriores.

O contrato dos resultados, o protocolo acordado e as pendências estão em
[`algoritmos/classicos/README.md`](algoritmos/classicos/README.md).
O [guia dos scripts](scripts/README.md) apresenta o comando principal e a
finalidade de cada entrada. As três primeiras rodadas foram executadas pelo
pesquisador. A [revisão do round3](analise/rodadas/round3_revisao.md) orientou o
plano de [18 configurações do round4](scripts/limiarizacao/rodadas/round4.json),
nos mesmos 178 quadros: 3.204 avaliações, com PDF automático ao concluir.
O mesmo [executor](scripts/limiarizacao/executar_rodada.py) atende a todas as
rodadas. Use `--rodada round4` para o próximo batch; sem argumentos, o padrão
continua sendo `round1`. Os planos de [round1](scripts/limiarizacao/rodadas/round1.json),
[round2](scripts/limiarizacao/rodadas/round2.json) e
[round3](scripts/limiarizacao/rodadas/round3.json) permanecem disponíveis para repetição.
Estão previstas cinco rodadas de desenvolvimento; o plano do round5 depende
dos resultados do round4. A avaliação final permanece posterior, conforme o
[protocolo](analise/protocolo_rodadas.md).
Para uma única imagem, há comandos separados de inspeção visual e avaliação.
Os detalhes estão no [guia de limiarização](scripts/limiarizacao/README.md) e
as regras das métricas, no [guia de avaliação](analise/README.md).
O macro-F1 de cada configuração está em `resumo_configuracoes.csv`, na pasta
do batch. O executor também gera um PDF com gráficos e estatísticas; o
[guia de avaliação](analise/README.md) explica como gerar o relatório de uma
rodada já concluída.
As execuções dos algoritmos, avaliações, testes e experimentos serão feitas pelo pesquisador.

## Versão anterior

- Código e documentos: branch `master`, commit `a218a3f45158af7238f6f6ff6302c0de33d97da1`.
- Arquivos locais, resultados, ambientes Python e piloto YOLO:
  `../my_tcc_historico_20260914/`.
- Orientações de recuperação: `../my_tcc_historico_20260914/PRESERVACAO_20260914.md`.

## Forma de trabalho

Cada próxima etapa será explicada e dependerá de autorização explícita do
pesquisador. O foco inicial é detecção de objetos em imagens e depois em
vídeos, quadro a quadro. Rastreamento, fluxo e predição serão discutidos
posteriormente. Os resultados serão organizados em `resultados/frame-to-frame/`
e `resultados/videos/`, por algoritmo, configuração e execução.
