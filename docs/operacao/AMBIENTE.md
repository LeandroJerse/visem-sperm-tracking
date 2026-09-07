# Ambiente reproduzível

O alvo do projeto é Python 3.11 ou superior, abaixo de 3.14. Nesta retomada a
máquina só disponibilizava CPython 3.13.3; a suíte curta foi validada nessa
versão. Isso deve ser registrado na metodologia em vez de declarar uma versão
3.11 que não foi executada localmente.

## Ambiente clássico/CPU validado

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-core.lock
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest
```

Em uma máquina com Python 3.11 instalado, troque apenas `-3.13` por `-3.11` e
rode a mesma suíte. `requirements-core.lock` fixa o ambiente headless usado nos
testes; `requirements.txt` descreve o ambiente completo do TCC.

## GPU e modelos opcionais

RAFT, LSTM e YOLO usam PyTorch/torchvision/Ultralytics e não fazem parte do lock
CPU. Instale uma combinação de PyTorch compatível com o driver/CUDA da máquina,
depois instale as demais dependências de `requirements.txt`. Registre no
manifest a versão efetivamente usada e confirme:

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

O wrapper RAFT usa pesos pré-treinados apenas quando solicitado; isso pode
exigir download na primeira execução. Um RAFT sem pesos serve para testar a
arquitetura, não é um baseline científico válido.

## Dois perfis OpenCV

O lock usa `opencv-python-headless`, adequado às baterias e CI. Para a bancada
interativa que abre janelas, substitua-o por `opencv-python` no ambiente local;
não instale os dois simultaneamente. Vídeos MP4 gerados pelo pipeline não exigem
que a interface gráfica esteja instalada.
