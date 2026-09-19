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
O primeiro script de inspeção individual está em
[`scripts/testar_limiarizacao_imagem.py`](scripts/testar_limiarizacao_imagem.py).
Ele salva a comparação visual, as tabelas e a configuração de uma imagem.
Consulte [`scripts/README.md`](scripts/README.md) para preencher a configuração
e executar. Não há métricas, lotes ou processamento de vídeos nesse script.
O avaliador dos resultados salvos está em
[`scripts/avaliar_deteccao_imagem.py`](scripts/avaliar_deteccao_imagem.py).
Ele compara localização e classe e produz uma análise auxiliar somente de
localização. As regras, a convenção de classes sem casos e os comandos estão em
[`analise/README.md`](analise/README.md).
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
