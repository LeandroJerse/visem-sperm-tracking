# TCC — reinício acompanhado

Branch: `codex/avaliacao-deteccao`.

Esta versão foi reiniciada com as bases existentes, em `bases_de_dados/`.
Consulte `bases_de_dados/LEIA_PRIMEIRO.md` para localizar vídeos, imagens e
anotações. Os arquivos pesados permanecem locais; não estão armazenados no Git.

O primeiro método está escrito em `algoritmos/classicos/limiarizacao.py`:
limiarização manual ou Otsu, abertura, fechamento e componentes conectados.
Ele ainda não foi executado nem validado experimentalmente nesta versão.
Blobs e Watershed serão implementados em etapas posteriores.

O contrato dos resultados, o protocolo acordado e as pendências estão em
[`algoritmos/classicos/README.md`](algoritmos/classicos/README.md).
Os scripts de execução ainda não foram criados. As execuções dos algoritmos
e experimentos serão feitas pelo pesquisador.

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
