"""Watershed da distância, com marcadores e caixas de regiões segmentadas.

Recebe somente imagem e parâmetros. Não consulta anotações nem escolhe limites.
"""

from dataclasses import dataclass, fields

import cv2
import numpy as np
from scipy import ndimage as ndi
from skimage.segmentation import watershed

from .classificacao import ConfiguracaoArea
from .comum import Caixa, ClasseObjeto, Deteccao, MedidasObjeto, ResultadoDeteccao, validar_real
from .limiarizacao import (
    ConfiguracaoLimiarizacao, ConfiguracaoMorfologia, _aplicar_morfologia, _imagem_cinza,
)


@dataclass(frozen=True)
class ConfiguracaoWatershed:
    segmentacao: ConfiguracaoLimiarizacao
    fracao_semente: float
    politica_aglomerados: str

    def __post_init__(self):
        if not isinstance(self.segmentacao, ConfiguracaoLimiarizacao):
            raise TypeError("segmentacao deve ser ConfiguracaoLimiarizacao.")
        validar_real("fracao_semente", self.fracao_semente)
        if not 0 < self.fracao_semente <= 1:
            raise ValueError("fracao_semente deve pertencer a (0, 1].")
        if self.politica_aglomerados not in ("separar", "preservar_por_area"):
            raise ValueError("politica_aglomerados deve ser separar ou preservar_por_area.")


def configuracao_de_dict(dados: dict) -> ConfiguracaoWatershed:
    """Parser estrito, sem valores implícitos ou chaves ignoradas."""
    def conferir(obj, classe):
        if not isinstance(obj, dict) or set(obj) != {f.name for f in fields(classe)}:
            raise ValueError(f"Campos inválidos em {classe.__name__}.")
    conferir(dados, ConfiguracaoWatershed)
    p = dados["segmentacao"]
    conferir(p, ConfiguracaoLimiarizacao)
    for chave in ("abertura", "fechamento"):
        conferir(p[chave], ConfiguracaoMorfologia)
    conferir(p["classificacao"], ConfiguracaoArea)
    segmentacao = ConfiguracaoLimiarizacao(**{
        **p, "abertura": ConfiguracaoMorfologia(**p["abertura"]),
        "fechamento": ConfiguracaoMorfologia(**p["fechamento"]),
        "classificacao": ConfiguracaoArea(**p["classificacao"]),
    })
    return ConfiguracaoWatershed(segmentacao, dados["fracao_semente"], dados["politica_aglomerados"])


@dataclass(frozen=True)
class InspecaoWatershed:
    resultado: ResultadoDeteccao
    mascara: np.ndarray
    distancia: np.ndarray
    componentes: np.ndarray
    marcadores: np.ndarray
    regioes: np.ndarray
    candidatos: tuple[dict, ...]
    componentes_info: tuple[dict, ...]


def inspecionar(imagem: np.ndarray, config: ConfiguracaoWatershed) -> InspecaoWatershed:
    """Segmenta, cria sementes por componente e mede cada região candidata.

    Sementes são componentes conectados de distância >= fração * máximo LOCAL.
    Cada componente tem ao menos uma semente, inclusive objetos pequenos ou na
    borda. A distância euclidiana usa um pixel de fundo ao redor da imagem.
    Watershed opera em -distância, restrito à máscara, sem remover divisórias.
    Todos os pixels da máscara pertencem a exatamente uma região candidata.

    preservar_por_area reúne as regiões de um componente cuja área original
    (após morfologia) alcança o limite de aglomerado. Não emite pai e filhos
    simultaneamente. Área, classe e filtros finais usam a região resultante.
    Essa regra é uma hipótese geométrica, não uma identificação biológica.
    """
    if not isinstance(config, ConfiguracaoWatershed):
        raise TypeError("config deve ser ConfiguracaoWatershed.")
    cinza = _imagem_cinza(imagem)
    p = config.segmentacao
    tipo = cv2.THRESH_BINARY if p.polaridade == "claro" else cv2.THRESH_BINARY_INV
    if p.metodo == "otsu":
        tipo |= cv2.THRESH_OTSU
    limiar, mascara = cv2.threshold(cinza, p.limiar_manual or 0, 255, tipo)
    mascara = _aplicar_morfologia(mascara, p.abertura, cv2.MORPH_OPEN)
    mascara = _aplicar_morfologia(mascara, p.fechamento, cv2.MORPH_CLOSE)
    estrutura = ndi.generate_binary_structure(2, 1 if p.conectividade == 4 else 2)
    componentes, quantidade = ndi.label(mascara != 0, structure=estrutura)
    componentes = componentes.astype(np.int32)
    distancia = ndi.distance_transform_edt(np.pad(mascara != 0, 1))[1:-1, 1:-1]
    marcadores = np.zeros(cinza.shape, np.int32)
    infos, total_sementes = [], 0
    for comp_id, recorte in enumerate(ndi.find_objects(componentes), 1):
        regiao = componentes[recorte] == comp_id
        dist = distancia[recorte]
        maximo = float(dist[regiao].max())
        sementes, n = ndi.label(regiao & (dist >= config.fracao_semente * maximo), structure=estrutura)
        view = marcadores[recorte]
        view[sementes > 0] = sementes[sementes > 0] + total_sementes
        area = int(regiao.sum())
        preservar = (config.politica_aglomerados == "preservar_por_area"
                     and p.classificacao.classificar(area) == ClasseObjeto.AGLOMERADO)
        infos.append({"componente_id": comp_id, "area_componente_px": area,
                      "sementes": int(n), "distancia_maxima_px": maximo,
                      "preservado_por_area": preservar,
                      "primeiro_marcador": total_sementes + 1})
        total_sementes += n
    if quantidade:
        regioes = watershed(-distancia, marcadores, connectivity=estrutura,
                            mask=mascara != 0, compactness=0, watershed_line=False).astype(np.int32)
    else:
        regioes = np.zeros(cinza.shape, np.int32)
    for info, recorte in zip(infos, ndi.find_objects(componentes)):
        if info["preservado_por_area"]:
            regioes[recorte][componentes[recorte] == info["componente_id"]] = info["primeiro_marcador"]

    candidatos, aceitas = [], []
    for regiao_id, recorte in enumerate(ndi.find_objects(regioes), 1):
        if recorte is None:
            continue
        mask = regioes[recorte] == regiao_id
        yy, xx = np.nonzero(mask)
        area = int(len(xx))
        comp_id = int(componentes[recorte][yy[0], xx[0]])
        info = infos[comp_id - 1]
        y, x = recorte[0].start, recorte[1].start
        h, w = recorte[0].stop - y, recorte[1].stop - x
        classe = p.classificacao.classificar(area)
        motivo = ("area_abaixo_minimo" if area < p.area_minima else
                  "area_acima_maximo" if p.area_maxima is not None and area > p.area_maxima else "aceito")
        candidato = {"regiao_id": regiao_id, "componente_id": comp_id,
                     "area_componente_px": info["area_componente_px"],
                     "sementes_componente": info["sementes"],
                     "preservado_por_area": info["preservado_por_area"],
                     "area_pixels": area, "classe": int(classe), "situacao": motivo,
                     "indice_deteccao": None, "caixa_x_px": x, "caixa_y_px": y,
                     "caixa_largura_px": w, "caixa_altura_px": h}
        candidatos.append(candidato)
        if motivo == "aceito":
            medidas = MedidasObjeto(area_pixels=area, centroide_x=float(xx.mean()) + x,
                                    centroide_y=float(yy.mean()) + y, area_caixa=w*h,
                                    alongamento=max(w, h)/min(w, h), ocupacao=area/(w*h),
                                    intensidade_media=float(cinza[recorte][mask].mean()))
            aceitas.append((Deteccao(classe, Caixa(x, y, w, h), medidas), candidato))
    aceitas.sort(key=lambda par: (par[0].caixa.y, par[0].caixa.x, par[1]["regiao_id"]))
    for indice, (_, candidato) in enumerate(aceitas):
        candidato["indice_deteccao"] = indice
    altura, largura = cinza.shape
    resultado = ResultadoDeteccao("watershed", largura, altura, tuple(d for d, _ in aceitas), float(limiar))
    return InspecaoWatershed(resultado, mascara, distancia.astype(np.float32), componentes,
                             marcadores, regioes, tuple(candidatos), tuple(infos))


def detectar(imagem: np.ndarray, config: ConfiguracaoWatershed) -> ResultadoDeteccao:
    return inspecionar(imagem, config).resultado
