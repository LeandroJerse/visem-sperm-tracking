# Cronograma de Estudos — TCC Rastreamento de Espermatozoides

Início: 27/04/2026 — 12 semanas

---

## Semana 1–2 (27/04 – 10/05) — Fundamentos de Visão Computacional

**O que estudar:**
- Representação de imagens: canais, espaços de cor (RGB, HSV, grayscale)
- Thresholding (global, Otsu, adaptativo)
- Transformações morfológicas: erosão, dilatação, abertura, fechamento
- Detecção de blobs (SimpleBlobDetector do OpenCV)
- Leitura e iteração de frames de vídeo com OpenCV

**Objetivo prático:** abrir um dos vídeos do TCC, segmentar os espermatozoides quadro a quadro e destacá-los com bounding boxes.

**Recursos:**
- [OpenCV Python Tutorials](https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html) — seções Core Operations e Image Processing
- Livro: *Programming Computer Vision with Python* (Jan Erik Solem) — caps. 1–3

---

## Semana 3–4 (11/05 – 24/05) — Fluxo Óptico Clássico

**O que estudar:**
- Equação do fluxo óptico (restrição de brilho constante)
- **Lucas-Kanade** sparse: rastreia pontos de interesse entre frames
- **Farneback** dense: campo de velocidade para todos os pixels
- Horn-Schunck: base teórica (leitura, não implementação)
- Visualização de campos vetoriais (HSV colormap, quiver plots)

**Objetivo prático:** rodar Farneback nos vídeos e visualizar a corrente do fluido como campo de vetores. Comparar visualmente regiões com e sem corrente.

**Recursos:**
- [OpenCV Optical Flow Tutorial](https://docs.opencv.org/4.x/d4/dee/tutorial_optical_flow.html)
- Paper original: *"Two-Frame Motion Estimation Based on Polynomial Expansion"* (Farneback, 2003)

---

## Semana 5–6 (25/05 – 07/06) — Filtro de Kalman e Rastreamento Clássico

**O que estudar:**
- Filtro de Kalman: modelo de estado, predição e correção (etapas predict/update)
- Definição de matriz de transição para movimento constante
- **Algoritmo Húngaro** (Hungarian): associação de detecções entre frames
- **SORT** (Simple Online Realtime Tracking): combina Kalman + Hungarian
- Métricas MOT: MOTA, MOTP, HOTA

**Objetivo prático:** implementar SORT sobre as detecções da Semana 1–2 e gerar as primeiras trajetórias com IDs persistentes.

**Recursos:**
- `filterpy` — [documentação e exemplos de Kalman](https://filterpy.readthedocs.io)
- Paper: *"Simple Online and Realtime Tracking"* (Bewley et al., 2016)
- `scipy.optimize.linear_sum_assignment` — implementação do Hungarian

---

## Semana 7–8 (08/06 – 21/06) — Fluxo Óptico com Deep Learning

**O que estudar:**
- Arquitetura geral de redes para optical flow (encoder-decoder, correlation layer)
- **RAFT** (Recurrent All-Pairs Field Transforms): iterative refinement com GRU
- Comparação quantitativa Farneback vs. RAFT: EPE (End-Point Error)
- Como usar modelo pré-treinado RAFT no PyTorch

**Objetivo prático:** rodar RAFT nos mesmos vídeos da Semana 3–4 e comparar o campo de fluxo. Quantificar diferença na região da corrente do tubo.

**Recursos:**
- Paper: *"RAFT: Recurrent All-Pairs Field Transforms for Optical Flow"* (Teed & Deng, 2020)
- Repositório oficial: `princeton-vl/RAFT` no GitHub

---

## Semana 9–10 (22/06 – 05/07) — Rastreamento Moderno

**O que estudar:**
- **DeepSORT**: SORT + embedding de aparência (re-identification network)
- **ByteTrack**: associação em dois estágios incluindo detecções de baixa confiança
- Diferença prática entre SORT / DeepSORT / ByteTrack para objetos pequenos
- Avaliação com HOTA

**Objetivo prático:** rodar ByteTrack sobre as detecções e comparar HOTA com o SORT da Semana 5–6. Gerar vídeo anotado com trajetórias.

**Recursos:**
- Paper: *"ByteTrack: Multi-Object Tracking by Associating Every Detection Box"* (Zhang et al., 2022)
- Repositório: `ifzhang/ByteTrack` no GitHub
- [py-motmetrics](https://github.com/cheind/py-motmetrics) — cálculo de MOTA/HOTA

---

## Semana 11–12 (06/07 – 19/07) — Predição de Trajetória

**O que estudar:**
- Formulação do problema: dado histórico (x₁..xₜ) + campo de fluxo → prever (xₜ₊₁..xₜ₊ₙ)
- **Kalman como baseline de predição**
- **LSTM/GRU**: sequência de posições como entrada, próxima posição como saída
- Como incorporar o campo de fluxo como feature auxiliar no LSTM
- Métricas: ADE (Average Displacement Error) e FDE (Final Displacement Error)

**Objetivo prático:** treinar LSTM simples com posição + vetor de fluxo na posição atual. Comparar ADE/FDE contra o baseline Kalman.

**Recursos:**
- Paper: *"Social LSTM: Human Trajectory Prediction in Crowded Spaces"* (Alahi et al., 2016)
- [PyTorch Sequence Models Tutorial](https://pytorch.org/tutorials/beginner/nlp/sequence_models_tutorial.html)

---

## Resumo

| Semanas | Tema | Entregável |
|---|---|---|
| 1–2 | OpenCV, segmentação | Detecção de espermatozoides quadro a quadro |
| 3–4 | Optical flow clássico | Campo de fluxo do fluido (Farneback) |
| 5–6 | Kalman + SORT | Trajetórias com IDs persistentes |
| 7–8 | RAFT (deep optical flow) | Comparação Farneback vs. RAFT |
| 9–10 | ByteTrack / DeepSORT | Avaliação HOTA, vídeo anotado |
| 11–12 | LSTM + predição | ADE/FDE vs. baseline Kalman |
