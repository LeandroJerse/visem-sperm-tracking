"""Compatibilidade entre medidas segmentadas e estimadas, sem acessar a base."""

import csv
from io import StringIO
import math
import unittest

from algoritmos.classicos.classificacao import ConfiguracaoArea, ConfiguracaoAreaEstimada
from algoritmos.classicos.comum import (
    Caixa, ClasseObjeto, Deteccao, MedidasBlob, MedidasObjeto, ResultadoDeteccao,
)
from scripts.limiarizacao.inspecionar_imagem import CAMPOS_DETECCAO


class CompatibilidadeMedidas(unittest.TestCase):
    def test_registro_segmentado_permanece_compativel_com_exportador_antigo(self):
        medidas = MedidasObjeto(8, 2.5, 3.5, 12, 4 / 3, 8 / 12, 125.0)
        objeto = Deteccao(ClasseObjeto.NORMAL, Caixa(1, 2, 3, 4), medidas)
        resultado = ResultadoDeteccao("limiarizacao", 10, 20, (objeto,), 100.0)
        registro = resultado.registros()[0]
        self.assertEqual(set(registro), set(CAMPOS_DETECCAO))
        self.assertEqual(registro["area_pixels"], 8)
        self.assertEqual(registro["centroide_x_px"], 2.5)
        self.assertEqual(registro["ocupacao_caixa"], 8 / 12)
        self.assertEqual(resultado.linhas_yolo(), ("0 0.25 0.2 0.3 0.2",))
        saida = StringIO()
        writer = csv.DictWriter(saida, fieldnames=CAMPOS_DETECCAO)
        writer.writeheader()
        writer.writerow(registro)
        self.assertEqual(len(list(csv.DictReader(StringIO(saida.getvalue())))), 1)

    def test_medidas_estimadas_nao_inventam_segmentacao(self):
        medidas = MedidasBlob(1.0, 1.0, 10.0, math.pi * 25, 36, True)
        objeto = Deteccao(ClasseObjeto.NORMAL, Caixa(0, 0, 6, 6), medidas)
        resultado = ResultadoDeteccao("blobs", 20, 20, (objeto,), None)
        registro = resultado.registros()[0]
        for campo in ("area_pixels", "centroide_x_px", "centroide_y_px",
                      "ocupacao_caixa", "intensidade_media", "limiar_utilizado"):
            self.assertIsNone(registro[campo], campo)
        self.assertEqual(registro["origem_medidas"], "simpleblob_keypoint")
        self.assertEqual(registro["centro_blob_x_px"], 1.0)
        self.assertTrue(registro["caixa_recortada_na_borda"])
        self.assertGreater(registro["area_estimada_blob_px2"], registro["area_caixa_px2"])
        self.assertEqual(resultado.linhas_yolo(), ("0 0.15 0.15 0.3 0.3",))

    def test_validacao_segmentada_permanece_estrita(self):
        with self.assertRaises(ValueError):
            MedidasObjeto(20, 1.0, 1.0, 12, 1.0, 1.0, 125.0)
        medidas = MedidasObjeto(8, 20.0, 1.0, 12, 1.0, 0.5, 125.0)
        with self.assertRaises(ValueError):
            Deteccao(ClasseObjeto.NORMAL, Caixa(0, 0, 3, 4), medidas)

    def test_estimativa_inconsistente_ou_nao_finita_e_rejeitada(self):
        for area in (0.0, -1.0, 1.0, math.inf, math.nan, True):
            with self.subTest(area=area), self.assertRaises((ValueError, TypeError)):
                MedidasBlob(2.0, 2.0, 4.0, area, 16, False)
        with self.assertRaises(TypeError):
            MedidasBlob(2.0, 2.0, 4.0, math.pi * 4, 16, 0)

    def test_centro_e_caixa_devem_ser_compativeis(self):
        medidas = MedidasBlob(9.0, 1.0, 4.0, math.pi * 4, 16, False)
        with self.assertRaises(ValueError):
            Deteccao(ClasseObjeto.NORMAL, Caixa(0, 0, 4, 4), medidas)

    def test_area_estimada_preserva_fronteiras_reais(self):
        limite = math.pi * 16
        config = ConfiguracaoAreaEstimada(limite, math.pi * 144)
        self.assertEqual(config.classificar(limite), ClasseObjeto.PEQUENO)
        self.assertEqual(config.classificar(math.nextafter(limite, math.inf)), ClasseObjeto.NORMAL)
        self.assertEqual(config.classificar(math.pi * 144), ClasseObjeto.AGLOMERADO)
        self.assertEqual(config.classificar(math.nextafter(math.pi * 144, 0)), ClasseObjeto.NORMAL)
        with self.assertRaises(TypeError):
            ConfiguracaoArea(40.5, 150)

    def test_limites_estimados_invalidos(self):
        for limites in ((0, 10), (10, 10), (20, 10), (True, 10), (1, math.inf)):
            with self.subTest(limites=limites), self.assertRaises((ValueError, TypeError)):
                ConfiguracaoAreaEstimada(*limites)


if __name__ == "__main__":
    unittest.main()
