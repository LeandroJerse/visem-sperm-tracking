"""Regra inicial por área segmentada; os limites exigem calibração."""

from dataclasses import dataclass

from .comum import ClasseObjeto, validar_inteiro, validar_real


@dataclass(frozen=True, slots=True)
class ConfiguracaoArea:
    """Limites explícitos em pixels da região, não em área da caixa.

    Região <= area_maxima_pequeno: classe 2.
    Região >= area_minima_aglomerado: classe 1.
    Região entre esses limites: classe 0.

    É uma hipótese de classificação, não uma equivalência biológica.
    O filtro que exclui regiões indesejadas pertence ao detector.
    """

    area_maxima_pequeno: int
    area_minima_aglomerado: int

    def __post_init__(self) -> None:
        validar_inteiro("area_maxima_pequeno", self.area_maxima_pequeno, 1)
        validar_inteiro("area_minima_aglomerado", self.area_minima_aglomerado, 1)
        if self.area_minima_aglomerado <= self.area_maxima_pequeno + 1:
            raise ValueError("Deve existir uma faixa inteira intermediária para a classe 0.")

    def classificar(self, area_pixels: int) -> ClasseObjeto:
        validar_inteiro("area_pixels", area_pixels, 1)
        if area_pixels <= self.area_maxima_pequeno:
            return ClasseObjeto.PEQUENO
        if area_pixels >= self.area_minima_aglomerado:
            return ClasseObjeto.AGLOMERADO
        return ClasseObjeto.NORMAL


@dataclass(frozen=True, slots=True)
class ConfiguracaoAreaEstimada:
    """Limites reais para área de círculo estimado, não para pixels segmentados."""

    area_maxima_pequeno: float
    area_minima_aglomerado: float

    def __post_init__(self) -> None:
        for nome in ("area_maxima_pequeno", "area_minima_aglomerado"):
            valor = getattr(self, nome)
            validar_real(nome, valor)
            if valor <= 0:
                raise ValueError(f"{nome} deve ser positivo.")
        if self.area_minima_aglomerado <= self.area_maxima_pequeno:
            raise ValueError("O limite de aglomerado deve superar o limite de pequeno.")

    def classificar(self, area_estimada: float) -> ClasseObjeto:
        validar_real("area_estimada", area_estimada)
        if area_estimada <= 0:
            raise ValueError("area_estimada deve ser positiva.")
        if area_estimada <= self.area_maxima_pequeno:
            return ClasseObjeto.PEQUENO
        if area_estimada >= self.area_minima_aglomerado:
            return ClasseObjeto.AGLOMERADO
        return ClasseObjeto.NORMAL
