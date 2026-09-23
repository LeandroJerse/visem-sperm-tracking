"""Representação comum de detecções, sem leitura ou gravação de arquivos."""

from dataclasses import dataclass
from enum import IntEnum
from math import isclose, isfinite, pi, sqrt
from numbers import Integral, Real


class ClasseObjeto(IntEnum):
    """Identificadores originais do VISEM-Tracking."""

    NORMAL = 0
    AGLOMERADO = 1
    PEQUENO = 2


def validar_inteiro(nome: str, valor: int, minimo: int = 0) -> None:
    """Rejeita valores fracionários e booleanos em parâmetros inteiros."""
    if isinstance(valor, bool) or not isinstance(valor, Integral):
        raise TypeError(f"{nome} deve ser um inteiro.")
    if valor < minimo:
        raise ValueError(f"{nome} deve ser maior ou igual a {minimo}.")


def validar_real(nome: str, valor: float) -> None:
    if isinstance(valor, bool) or not isinstance(valor, Real):
        raise TypeError(f"{nome} deve ser um número real.")
    if not isfinite(valor):
        raise ValueError(f"{nome} deve ser finito.")


@dataclass(frozen=True, slots=True)
class Caixa:
    """Retângulo em pixels: origem inclusiva, limite direito/inferior exclusivo."""

    x: int
    y: int
    largura: int
    altura: int

    def __post_init__(self) -> None:
        validar_inteiro("x", self.x)
        validar_inteiro("y", self.y)
        validar_inteiro("largura", self.largura, 1)
        validar_inteiro("altura", self.altura, 1)

    def normalizada(
        self, largura_imagem: int, altura_imagem: int
    ) -> tuple[float, float, float, float]:
        """Retorna centro_x, centro_y, largura e altura no padrão YOLO."""
        validar_inteiro("largura_imagem", largura_imagem, 1)
        validar_inteiro("altura_imagem", altura_imagem, 1)
        if self.x + self.largura > largura_imagem:
            raise ValueError("A caixa ultrapassa a largura da imagem.")
        if self.y + self.altura > altura_imagem:
            raise ValueError("A caixa ultrapassa a altura da imagem.")
        return (
            (self.x + self.largura / 2) / largura_imagem,
            (self.y + self.altura / 2) / altura_imagem,
            self.largura / largura_imagem,
            self.altura / altura_imagem,
        )


@dataclass(frozen=True, slots=True)
class MedidasObjeto:
    """Medidas da região binária e da imagem em cinza antes da segmentação."""

    area_pixels: int
    centroide_x: float
    centroide_y: float
    area_caixa: int
    alongamento: float
    ocupacao: float
    intensidade_media: float

    def __post_init__(self) -> None:
        validar_inteiro("area_pixels", self.area_pixels, 1)
        validar_inteiro("area_caixa", self.area_caixa, 1)
        for nome in (
            "centroide_x", "centroide_y", "alongamento", "ocupacao",
            "intensidade_media",
        ):
            validar_real(nome, getattr(self, nome))
        if self.area_pixels > self.area_caixa:
            raise ValueError("A região não pode ter área maior que sua caixa.")
        if self.alongamento < 1:
            raise ValueError("alongamento deve ser maior ou igual a 1.")
        if not 0 < self.ocupacao <= 1:
            raise ValueError("ocupacao deve estar no intervalo (0, 1].")
        if not 0 <= self.intensidade_media <= 255:
            raise ValueError("intensidade_media deve estar entre 0 e 255.")


@dataclass(frozen=True, slots=True)
class MedidasBlob:
    """Geometria estimada por keypoint ou escala; não é uma região segmentada."""

    centro_blob_x: float
    centro_blob_y: float
    diametro_blob: float
    area_estimada_blob: float
    area_caixa: int
    caixa_recortada_na_borda: bool
    origem_medidas: str = "simpleblob_keypoint"
    sigma_blob: float | None = None

    def __post_init__(self) -> None:
        for nome in ("centro_blob_x", "centro_blob_y", "diametro_blob", "area_estimada_blob"):
            validar_real(nome, getattr(self, nome))
        if self.centro_blob_x < 0 or self.centro_blob_y < 0:
            raise ValueError("O centro estimado não pode ter coordenadas negativas.")
        if self.diametro_blob <= 0 or self.area_estimada_blob <= 0:
            raise ValueError("Diâmetro e área estimados devem ser positivos.")
        # Preserva a estimativa anterior ao recorte da caixa na borda da imagem.
        raio = self.diametro_blob / 2
        esperada = pi * raio * raio
        if not isfinite(esperada) or not isclose(
            self.area_estimada_blob, esperada, rel_tol=1e-12, abs_tol=0.0
        ):
            raise ValueError("A área estimada deve corresponder a pi * (diâmetro/2)^2.")
        validar_inteiro("area_caixa", self.area_caixa, 1)
        if type(self.caixa_recortada_na_borda) is not bool:
            raise TypeError("caixa_recortada_na_borda deve ser booleana.")
        if not isinstance(self.origem_medidas, str) or self.origem_medidas not in (
            "simpleblob_keypoint", "log_sigma", "dog_sigma",
        ):
            raise ValueError("origem_medidas deve identificar keypoint, LoG ou DoG.")
        if self.origem_medidas == "simpleblob_keypoint":
            if self.sigma_blob is not None:
                raise ValueError("Keypoints SimpleBlobDetector não fornecem sigma.")
        else:
            validar_real("sigma_blob", self.sigma_blob)
            if self.sigma_blob <= 0:
                raise ValueError("sigma_blob deve ser positivo.")
            diametro_esperado = 2 * sqrt(2) * self.sigma_blob
            if not isfinite(diametro_esperado) or not isclose(
                self.diametro_blob, diametro_esperado, rel_tol=1e-12, abs_tol=0.0
            ):
                raise ValueError("O diâmetro de LoG/DoG deve ser 2 * sqrt(2) * sigma.")


@dataclass(frozen=True, slots=True)
class Deteccao:
    classe: ClasseObjeto
    caixa: Caixa
    medidas: MedidasObjeto | MedidasBlob

    def __post_init__(self) -> None:
        if not isinstance(self.classe, ClasseObjeto):
            raise TypeError("classe deve ser um membro de ClasseObjeto.")
        if not isinstance(self.caixa, Caixa):
            raise TypeError("caixa deve ser uma Caixa.")
        if not isinstance(self.medidas, (MedidasObjeto, MedidasBlob)):
            raise TypeError("medidas deve ser MedidasObjeto ou MedidasBlob.")
        if self.medidas.area_caixa != self.caixa.largura * self.caixa.altura:
            raise ValueError("area_caixa deve corresponder às dimensões da caixa.")
        if isinstance(self.medidas, MedidasBlob):
            centro_x, centro_y = self.medidas.centro_blob_x, self.medidas.centro_blob_y
        else:
            centro_x, centro_y = self.medidas.centroide_x, self.medidas.centroide_y
        if not self.caixa.x <= centro_x < self.caixa.x + self.caixa.largura:
            raise ValueError("centroide_x deve pertencer à caixa.")
        if not self.caixa.y <= centro_y < self.caixa.y + self.caixa.altura:
            raise ValueError("centroide_y deve pertencer à caixa.")


@dataclass(frozen=True, slots=True)
class ResultadoDeteccao:
    """Resultado de uma imagem; não atribui identidade persistente aos objetos."""

    algoritmo: str
    largura_imagem: int
    altura_imagem: int
    deteccoes: tuple[Deteccao, ...]
    limiar_utilizado: float | None

    def __post_init__(self) -> None:
        if not isinstance(self.algoritmo, str) or not self.algoritmo.strip():
            raise ValueError("algoritmo deve ser um nome não vazio.")
        validar_inteiro("largura_imagem", self.largura_imagem, 1)
        validar_inteiro("altura_imagem", self.altura_imagem, 1)
        if not isinstance(self.deteccoes, tuple):
            raise TypeError("deteccoes deve ser uma tupla.")
        if self.limiar_utilizado is not None:
            validar_real("limiar_utilizado", self.limiar_utilizado)
            if not 0 <= self.limiar_utilizado <= 255:
                raise ValueError("limiar_utilizado deve estar entre 0 e 255.")
        for deteccao in self.deteccoes:
            if not isinstance(deteccao, Deteccao):
                raise TypeError("Cada resultado deve ser uma Deteccao.")
            deteccao.caixa.normalizada(self.largura_imagem, self.altura_imagem)

    def linhas_yolo(self) -> tuple[str, ...]:
        """Monta as linhas class_id center_x center_y width height, sem gravar."""
        linhas = []
        for deteccao in self.deteccoes:
            caixa = deteccao.caixa.normalizada(self.largura_imagem, self.altura_imagem)
            coordenadas = " ".join(f"{valor:.12g}" for valor in caixa)
            linhas.append(f"{int(deteccao.classe)} {coordenadas}")
        return tuple(linhas)

    def registros(self) -> tuple[dict[str, int | float | str | None], ...]:
        """Monta registros para uma futura tabela; nenhum arquivo é criado."""
        registros = []
        for indice, deteccao in enumerate(self.deteccoes):
            caixa, medidas = deteccao.caixa, deteccao.medidas
            cx, cy, largura, altura = caixa.normalizada(
                self.largura_imagem, self.altura_imagem
            )
            estimada = isinstance(medidas, MedidasBlob)
            registro = {
                "algoritmo": self.algoritmo,
                "indice_deteccao": indice,
                "classe": int(deteccao.classe),
                "imagem_largura_px": self.largura_imagem,
                "imagem_altura_px": self.altura_imagem,
                "caixa_x_px": caixa.x,
                "caixa_y_px": caixa.y,
                "caixa_largura_px": caixa.largura,
                "caixa_altura_px": caixa.altura,
                "caixa_centro_x_norm": cx,
                "caixa_centro_y_norm": cy,
                "caixa_largura_norm": largura,
                "caixa_altura_norm": altura,
                "centroide_x_px": None if estimada else medidas.centroide_x,
                "centroide_y_px": None if estimada else medidas.centroide_y,
                "area_pixels": None if estimada else medidas.area_pixels,
                "area_caixa_px2": medidas.area_caixa,
                "alongamento_caixa": (
                    max(caixa.largura, caixa.altura) / min(caixa.largura, caixa.altura)
                    if estimada else medidas.alongamento
                ),
                "ocupacao_caixa": None if estimada else medidas.ocupacao,
                "intensidade_media": None if estimada else medidas.intensidade_media,
                "limiar_utilizado": self.limiar_utilizado,
            }
            if estimada:
                registro.update({
                    "origem_medidas": medidas.origem_medidas,
                    "centro_blob_x_px": medidas.centro_blob_x,
                    "centro_blob_y_px": medidas.centro_blob_y,
                    "diametro_blob_px": medidas.diametro_blob,
                    "area_estimada_blob_px2": medidas.area_estimada_blob,
                    "caixa_recortada_na_borda": medidas.caixa_recortada_na_borda,
                })
                if medidas.sigma_blob is not None:
                    registro["sigma_blob_px"] = medidas.sigma_blob
            registros.append(registro)
        return tuple(registros)
