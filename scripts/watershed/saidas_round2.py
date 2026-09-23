"""Saídas do Otsu ajustado; conserva os formatos históricos dos controles."""

from pathlib import Path
from time import perf_counter_ns

from analise.avaliacao_individuos import avaliar
from scripts.blobs.arquivos import gravar_json
from scripts.blobs.executar_inspecao import colunas_metricas, objetos
from scripts.limiarizacao.inspecionar_imagem import (
    CAMPOS_ANOTACAO, CAMPOS_DETECCAO, CAMPOS_ORIGEM, desenhar_painel, gravar_csv, identificar_origem,
)
from scripts.watershed.executar_inspecao import gravar_png
from scripts.watershed.executar_rodada import relativo


def executar_quadro(entrada, item, config, pasta):
    import cv2
    import numpy as np
    from algoritmos.classicos.variantes_watershed import inspecionar
    imagem, anotacoes, q = entrada["imagem"], entrada["anotacoes"], entrada["quadro"]
    pasta.mkdir(parents=True, exist_ok=False)
    origem = identificar_origem(Path(q["imagem"]), Path(q["anotacao"]))
    origem.update(imagem=q["imagem"], anotacao=q["anotacao"])
    inicio = perf_counter_ns()
    d, metadados = inspecionar(imagem, config)
    tempo = perf_counter_ns() - inicio
    gravar_json(pasta / "segmentacao.json", metadados)
    registros = list(d.resultado.registros())
    a = avaliar(objetos(anotacoes, "indice_anotacao"), objetos(registros, "indice_deteccao"))
    gravar_json(pasta / "avaliacao.json", a)
    gravar_json(pasta / "diagnostico.json", {"componentes": d.componentes_info, "candidatos": d.candidatos})
    gravar_csv(pasta / "deteccoes.csv", CAMPOS_ORIGEM + CAMPOS_DETECCAO, ({**origem, **r} for r in registros))
    gravar_csv(pasta / "anotacoes.csv", CAMPOS_ORIGEM + CAMPOS_ANOTACAO, ({**origem, **r} for r in anotacoes))
    campos_pares = ["indice_anotacao", "indice_deteccao", "classe_anotacao", "classe_deteccao", "iou", "grupo", "classe_correta"]
    gravar_csv(pasta / "pares.csv", campos_pares, a["pares"])
    pendentes = []
    for tipo, lista, chave, indice in (("FN", anotacoes, "anotacoes_sem_par", "indice_anotacao"),
                                      ("FP", registros, "deteccoes_sem_par", "indice_deteccao")):
        por_id = {r[indice]: r for r in lista}
        for idx in a[chave]:
            r = por_id[idx]
            pendentes.append({"tipo": tipo, "indice": idx, "classe": r["classe"],
                              **{k: r[k] for k in ("caixa_x_px", "caixa_y_px", "caixa_largura_px", "caixa_altura_px")}})
    gravar_csv(pasta / "pendentes.csv", ["tipo", "indice", "classe", "caixa_x_px", "caixa_y_px", "caixa_largura_px", "caixa_altura_px"], pendentes)
    (pasta / "predicoes.txt").write_text("".join(x + "\n" for x in d.resultado.linhas_yolo()), encoding="utf-8")
    np.savez_compressed(pasta / "mapas.npz", componentes=d.componentes, marcadores=d.marcadores,
                        regioes=d.regioes, distancia=d.distancia, mascara=d.mascara)
    gravar_png(pasta / "mascara.png", d.mascara, cv2)
    colorida = cv2.cvtColor(imagem, cv2.COLOR_GRAY2BGR) if imagem.ndim == 2 else imagem
    painel = np.concatenate((desenhar_painel(cv2, np, colorida, anotacoes, f"Anotacoes: {len(anotacoes)}"),
                             desenhar_painel(cv2, np, colorida, registros, f"Watershed {item['id']}: {len(registros)}")), axis=1)
    gravar_png(pasta / "comparacao.png", painel, cv2)
    rotulos = d.regioes.astype(np.int64)
    cores = np.stack([(rotulos * fator % 191 + 64).astype(np.uint8) for fator in (53, 97, 137)], axis=-1)
    cores[rotulos == 0] = 0
    sobreposta = cv2.addWeighted(colorida, .5, cores, .5, 0)
    sobreposta[d.marcadores > 0] = (255, 255, 255)
    gravar_png(pasta / "regioes_sementes.png", sobreposta, cv2)
    linha = {"configuracao_id": item["id"], **origem, "pasta_quadro": relativo(pasta),
             "componentes": len(d.componentes_info), "sementes": sum(i["sementes"] for i in d.componentes_info),
             "componentes_preservados": sum(i["preservado_por_area"] for i in d.componentes_info),
             "regioes_candidatas": len(d.candidatos), "deteccoes": len(registros),
             "rejeitadas_area": len(d.candidatos) - len(registros), "tempo_detector_ns": tempo,
             **colunas_metricas(a), **metadados}
    return linha, a


