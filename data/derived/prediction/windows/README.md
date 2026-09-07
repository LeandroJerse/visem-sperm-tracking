# Janelas de predição

Derivados opcionais para treino e auditoria dos preditores. Cada janela deve
pertencer a um único vídeo, split e `track_id`, usar frames consecutivos e
registrar histórico, horizontes e origem.

O executor atual constrói janelas de forma determinística a partir do CSV e
grava métricas na run; esta pasta só é necessária quando for útil materializar
ou cachear as janelas.
