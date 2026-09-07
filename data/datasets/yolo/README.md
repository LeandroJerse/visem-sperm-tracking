# Dataset YOLO

`official_12_4_4/` é a única definição válida para novos experimentos. O
comando de preparação está em `script/README.md` e gera `train.txt`, `val.txt`,
`test.txt` e `visem.yaml` a partir de `configs/protocol/splits.yaml`.

`legacy_16_4/` conserva o piloto anterior. Seus caminhos absolutos históricos
podem não existir após a reorganização; não o use para treinar o resultado
final.
