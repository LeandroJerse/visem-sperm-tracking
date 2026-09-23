"""Contrato LoG/DoG e CLAHE usando apenas matrizes sintéticas."""

import copy
from dataclasses import asdict, replace
import math
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from algoritmos.classicos.caixas_blobs import (
    adaptar_caixas, configuracao_caixa_de_dict,
)
from algoritmos.classicos.classificacao import ConfiguracaoAreaEstimada
from algoritmos.classicos.comum import (
    Caixa, ClasseObjeto, Deteccao, MedidasBlob, ResultadoDeteccao,
)
from algoritmos.classicos.variantes_blobs import (
    ConfiguracaoEscalaBlobs, aplicar_preprocessamento, configuracao_escala_de_dict,
    detectar_escala, parametros_escala, validar_preprocessamento,
)


def dados(metodo="log", **mudancas):
    valores = {
        "polaridade": "claro", "sigma_minimo": 1, "sigma_maximo": 10,
        "limiar_resposta": 0.04, "sobreposicao": 0.5,
        "classificacao": {"area_maxima_pequeno": 30, "area_minima_aglomerado": 300},
    }
    valores["numero_escalas" if metodo == "log" else "razao_sigma"] = 10 if metodo == "log" else 1.6
    valores.update(mudancas)
    return valores


class ConfiguracoesEscala(unittest.TestCase):
    def test_schema_canonico_e_entrada_preservada(self):
        for metodo in ("log", "dog"):
            entrada = dados(metodo)
            copia = copy.deepcopy(entrada)
            config = configuracao_escala_de_dict(metodo, entrada)
            self.assertEqual(entrada, copia)
            self.assertIsInstance(config, ConfiguracaoEscalaBlobs)
            self.assertEqual(config.metodo, metodo)
            self.assertIsInstance(config.sigma_minimo, float)
            self.assertIsInstance(config.classificacao.area_maxima_pequeno, float)
            self.assertIsNone(config.razao_sigma if metodo == "log" else config.numero_escalas)
            self.assertEqual(asdict(config)["classificacao"], entrada["classificacao"])

    def test_rejeita_campos_omitidos_extras_e_de_outro_metodo(self):
        for metodo in ("log", "dog"):
            for campo in dados(metodo):
                entrada = dados(metodo)
                entrada.pop(campo)
                with self.subTest(metodo=metodo, campo=campo), self.assertRaises(ValueError):
                    configuracao_escala_de_dict(metodo, entrada)
            for extra in ("metodo", "qualquer", "razao_sigma" if metodo == "log" else "numero_escalas"):
                entrada = dict(dados(metodo), **{extra: None})
                with self.subTest(extra=extra), self.assertRaises(ValueError):
                    configuracao_escala_de_dict(metodo, entrada)
        for invalido in (None, [], True, "log", 3):
            with self.subTest(invalido=invalido), self.assertRaises(TypeError):
                configuracao_escala_de_dict("log", invalido)

    def test_numeros_e_intervalos_invalidos(self):
        for campo in ("sigma_minimo", "sigma_maximo", "limiar_resposta", "sobreposicao"):
            for valor in (True, None, "1", math.nan, math.inf, -math.inf, 10**400):
                with self.subTest(campo=campo, valor=valor), self.assertRaises((TypeError, ValueError)):
                    configuracao_escala_de_dict("log", dados(**{campo: valor}))
        for alteracao in (
            {"sigma_minimo": 0}, {"sigma_minimo": 10}, {"sigma_maximo": 0.5},
            {"sigma_minimo": 1e-300}, {"sigma_maximo": 1e300},
            {"limiar_resposta": 0}, {"sobreposicao": -0.1}, {"sobreposicao": 1.1},
        ):
            with self.subTest(alteracao=alteracao), self.assertRaises(ValueError):
                configuracao_escala_de_dict("log", dados(**alteracao))

    def test_contagem_razao_e_polaridade_invalidas(self):
        for valor in (True, 1, 0, -2, 2.5, None, math.nan):
            with self.subTest(valor=valor), self.assertRaises((TypeError, ValueError)):
                configuracao_escala_de_dict("log", dados(numero_escalas=valor))
        for valor in (True, 1, 0.8, math.nan, math.inf, None):
            with self.subTest(valor=valor), self.assertRaises((TypeError, ValueError)):
                configuracao_escala_de_dict("dog", dados("dog", razao_sigma=valor))
        for valor in (None, True, "ambos", [], 0):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                configuracao_escala_de_dict("log", dados(polaridade=valor))
            with self.subTest(metodo=valor), self.assertRaises(ValueError):
                configuracao_escala_de_dict(valor, dados())

    def test_dataclass_direta_tambem_valida_o_campo_inativo(self):
        with self.assertRaises(ValueError):
            replace(configuracao_escala_de_dict("log", dados()), razao_sigma=1.6)
        with self.assertRaises(ValueError):
            replace(configuracao_escala_de_dict("dog", dados("dog")), numero_escalas=10)
        with self.assertRaises(TypeError):
            replace(configuracao_escala_de_dict("log", dados()), classificacao={})

    def test_classificacao_invalida_e_rejeitada(self):
        for valor in (None, {}, {"area_maxima_pequeno": 1, "area_minima_aglomerado": 2, "extra": 3},
                      {"area_maxima_pequeno": True, "area_minima_aglomerado": 2},
                      {"area_maxima_pequeno": 2, "area_minima_aglomerado": 2}):
            with self.subTest(valor=valor), self.assertRaises((TypeError, ValueError)):
                configuracao_escala_de_dict("log", dados(classificacao=valor))

    def test_parametros_explicitos_do_backend(self):
        comum = dict(min_sigma=1.0, max_sigma=10.0, threshold=0.04, overlap=0.5,
                     threshold_rel=None, exclude_border=False)
        self.assertEqual(parametros_escala(configuracao_escala_de_dict("log", dados())),
                         dict(comum, num_sigma=10, log_scale=False))
        self.assertEqual(parametros_escala(configuracao_escala_de_dict("dog", dados("dog"))),
                         dict(comum, sigma_ratio=1.6))
        with self.assertRaises(TypeError):
            parametros_escala({})


class Preprocessamento(unittest.TestCase):
    def test_nenhum_copia_cinza_e_converte_bgr(self):
        for entrada in (np.arange(90, dtype=np.uint8).reshape(9, 10),
                        np.arange(270, dtype=np.uint8).reshape(9, 10, 3)):
            antes = entrada.copy()
            saida = aplicar_preprocessamento(entrada, {"metodo": "nenhum"})
            esperado = entrada if entrada.ndim == 2 else cv2.cvtColor(entrada, cv2.COLOR_BGR2GRAY)
            np.testing.assert_array_equal(saida, esperado)
            np.testing.assert_array_equal(entrada, antes)
            self.assertFalse(np.shares_memory(saida, entrada))
            self.assertEqual(saida.dtype, np.uint8)

    def test_clahe_corresponde_ao_backend_e_preserva_entrada(self):
        entrada = np.tile(np.arange(64, dtype=np.uint8), (64, 1)) + 80
        antes = entrada.copy()
        config = {"metodo": "clahe", "limite_contraste": 2, "grade": [8, 8]}
        canonica = validar_preprocessamento(config)
        self.assertIsInstance(canonica["limite_contraste"], float)
        self.assertIsNot(canonica["grade"], config["grade"])
        saida = aplicar_preprocessamento(entrada, config)
        esperado = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(entrada)
        np.testing.assert_array_equal(saida, esperado)
        np.testing.assert_array_equal(entrada, antes)
        self.assertFalse(np.shares_memory(saida, entrada))
        self.assertEqual(config, {"metodo": "clahe", "limite_contraste": 2, "grade": [8, 8]})

    def test_configuracao_estrita(self):
        invalidas = [None, [], {}, {"metodo": "x"}, {"metodo": True},
                     {"metodo": "nenhum", "grade": [8, 8]},
                     {"metodo": "clahe", "grade": [8, 8]},
                     {"metodo": "clahe", "limite_contraste": 2, "grade": [8, 8], "x": 1}]
        for valor in (True, None, math.nan, math.inf, 0, -1):
            invalidas.append({"metodo": "clahe", "limite_contraste": valor, "grade": [8, 8]})
        for valor in ([True, 8], [8.0, 8], [0, 8], [8], [8, 8, 8], (8, 8), [2**32, 8]):
            invalidas.append({"metodo": "clahe", "limite_contraste": 2, "grade": valor})
        for entrada in invalidas:
            with self.subTest(entrada=entrada), self.assertRaises((TypeError, ValueError)):
                validar_preprocessamento(entrada)

    def test_imagens_invalidas_e_rejeitadas_antes_do_backend(self):
        for entrada in (None, [[1]], np.zeros((3, 3), np.float32), np.zeros((0, 3), np.uint8),
                        np.zeros((3, 3, 4), np.uint8), np.zeros((3,), np.uint8)):
            with self.subTest(tipo=type(entrada)), self.assertRaises((TypeError, ValueError)):
                aplicar_preprocessamento(entrada, {"metodo": "nenhum"})
            with self.subTest(detector=type(entrada)), self.assertRaises((TypeError, ValueError)):
                detectar_escala(entrada, configuracao_escala_de_dict("log", dados()))


class MedidasEscala(unittest.TestCase):
    def test_registro_sbd_mantem_exatamente_chaves_legadas(self):
        from scripts.blobs.executar_inspecao import CAMPOS_DETECCAO, CAMPOS_BLOBS
        medidas = MedidasBlob(10, 10, 4, math.pi * 4, 16, False)
        resultado = ResultadoDeteccao("blobs", 20, 20, (
            Deteccao(ClasseObjeto.NORMAL, Caixa(8, 8, 4, 4), medidas),
        ), None)
        registro = resultado.registros()[0]
        self.assertEqual(set(registro), set(CAMPOS_DETECCAO + CAMPOS_BLOBS))
        self.assertNotIn("sigma_blob_px", registro)
        self.assertEqual(registro["origem_medidas"], "simpleblob_keypoint")

    def test_proveniencia_sigma_diametro_e_rejeicao_de_contradicoes(self):
        sigma = 2.0
        diametro = 2 * math.sqrt(2) * sigma
        valores = dict(centro_blob_x=10, centro_blob_y=10, diametro_blob=diametro,
                       area_estimada_blob=math.pi * (diametro / 2) ** 2, area_caixa=36,
                       caixa_recortada_na_borda=False, origem_medidas="log_sigma", sigma_blob=sigma)
        for metodo in ("log", "dog"):
            medidas = MedidasBlob(**dict(valores, origem_medidas=metodo + "_sigma"))
            registro = ResultadoDeteccao("blobs", 20, 20, (
                Deteccao(ClasseObjeto.PEQUENO, Caixa(7, 7, 6, 6), medidas),
            ), None).registros()[0]
            self.assertEqual(registro["sigma_blob_px"], 2)
            self.assertEqual(registro["origem_medidas"], metodo + "_sigma")
            for campo in ("centroide_x_px", "area_pixels", "ocupacao_caixa", "intensidade_media"):
                self.assertIsNone(registro[campo])
        for alteracao in ({"sigma_blob": None}, {"sigma_blob": True}, {"sigma_blob": 0},
                          {"sigma_blob": 3}, {"sigma_blob": math.nan},
                          {"origem_medidas": "simpleblob_keypoint"}, {"origem_medidas": []}):
            with self.subTest(alteracao=alteracao), self.assertRaises((TypeError, ValueError)):
                MedidasBlob(**dict(valores, **alteracao))


class DeteccaoEscala(unittest.TestCase):
    def test_normalizacao_fixa_polaridades_e_kwargs(self):
        entrada = np.array([[0, 64], [128, 255]], dtype=np.uint8)
        for metodo in ("log", "dog"):
            for polaridade in ("claro", "escuro"):
                config = configuracao_escala_de_dict(metodo, dados(metodo, polaridade=polaridade))
                with patch("skimage.feature.blob_" + metodo, return_value=np.empty((0, 3))) as backend:
                    resultado = detectar_escala(entrada, config)
                esperada = entrada.astype(np.float64) / 255.0
                if polaridade == "escuro":
                    esperada = 1 - esperada
                np.testing.assert_array_equal(backend.call_args.args[0], esperada)
                self.assertEqual(backend.call_args.kwargs, parametros_escala(config))
                self.assertEqual(resultado.deteccoes, ())
                self.assertEqual(resultado.linhas_yolo(), ())
                self.assertEqual(resultado.registros(), ())
                self.assertEqual(resultado.algoritmo, "blobs")
                self.assertIsNone(resultado.limiar_utilizado)
        np.testing.assert_array_equal(entrada, [[0, 64], [128, 255]])

    def test_coordenadas_escala_arredondamento_recorte_e_classes(self):
        pontos = np.array([[25, 40, 4], [1, 2, 8], [20, 10, 1]], dtype=np.float64)
        for metodo in ("log", "dog"):
            config = configuracao_escala_de_dict(metodo, dados(metodo))
            with patch("skimage.feature.blob_" + metodo, return_value=pontos):
                resultado = detectar_escala(np.zeros((50, 70), np.uint8), config)
            self.assertEqual(len(resultado.deteccoes), 3)
            borda, pequeno, normal = resultado.deteccoes
            self.assertEqual((borda.medidas.centro_blob_x, borda.medidas.centro_blob_y), (2, 1))
            self.assertEqual(borda.classe, ClasseObjeto.AGLOMERADO)
            self.assertEqual(borda.caixa, Caixa(0, 0, 14, 13))
            self.assertTrue(borda.medidas.caixa_recortada_na_borda)
            self.assertAlmostEqual(borda.medidas.area_estimada_blob, 128 * math.pi)
            self.assertEqual(pequeno.classe, ClasseObjeto.PEQUENO)
            self.assertEqual(normal.classe, ClasseObjeto.NORMAL)
            self.assertEqual(normal.caixa, Caixa(34, 19, 12, 12))
            self.assertEqual(normal.medidas.sigma_blob, 4)
            self.assertEqual(normal.medidas.origem_medidas, metodo + "_sigma")
            self.assertFalse(normal.medidas.caixa_recortada_na_borda)
            for linha in resultado.linhas_yolo():
                self.assertTrue(all(0 <= float(v) <= 1 for v in linha.split()[1:]))

    def test_ordem_independe_da_ordem_do_backend(self):
        pontos = np.array([[20, 30, 2], [40, 40, 4], [2, 3, 1]], dtype=float)
        config = configuracao_escala_de_dict("log", dados())
        with patch("skimage.feature.blob_log", return_value=pontos):
            primeiro = detectar_escala(np.zeros((70, 80), np.uint8), config)
        with patch("skimage.feature.blob_log", return_value=pontos[::-1]):
            segundo = detectar_escala(np.zeros((70, 80), np.uint8), config)
        self.assertEqual(primeiro, segundo)

    def test_adaptacao_preserva_sigma_area_e_classe(self):
        with patch("skimage.feature.blob_log", return_value=np.array([[2, 3, 2]], dtype=float)):
            original = detectar_escala(np.zeros((40, 40), np.uint8), configuracao_escala_de_dict("log", dados()))
        adaptado = adaptar_caixas(original, configuracao_caixa_de_dict({"modo": "margem", "pixels": 8}))
        self.assertNotEqual(original.deteccoes[0].caixa, adaptado.deteccoes[0].caixa)
        self.assertEqual(original.deteccoes[0].classe, adaptado.deteccoes[0].classe)
        for nome in ("centro_blob_x", "centro_blob_y", "diametro_blob", "area_estimada_blob",
                     "origem_medidas", "sigma_blob"):
            self.assertEqual(getattr(original.deteccoes[0].medidas, nome), getattr(adaptado.deteccoes[0].medidas, nome))

    def test_saida_malformada_do_backend_falha_explicitamente(self):
        for valor in (np.array([]), np.zeros((1, 4)), np.array([[0, 0, 0]]),
                      np.array([[0, -1, 1]]), np.array([[10, 0, 1]]),
                      np.array([[0, 10, 1]]), np.array([[0, 0, math.inf]]),
                      np.array([[math.nan, 0, 1]]), np.array([[0, 0, 1e300]])):
            with self.subTest(valor=valor), patch("skimage.feature.blob_log", return_value=valor):
                with self.assertRaises(ValueError):
                    detectar_escala(np.zeros((10, 10), np.uint8), configuracao_escala_de_dict("log", dados()))

    def test_backend_real_duas_gaussianas_em_ambas_polaridades(self):
        y, x = np.indices((128, 128))
        sinais = np.exp(-((x - 32) ** 2 + (y - 40) ** 2) / (2 * 3**2))
        sinais += np.exp(-((x - 92) ** 2 + (y - 86) ** 2) / (2 * 6**2))
        claro = np.rint(sinais * 255).clip(0, 255).astype(np.uint8)
        for metodo in ("log", "dog"):
            for polaridade in ("claro", "escuro"):
                entrada = claro if polaridade == "claro" else 255 - claro
                antes = entrada.copy()
                resultado = detectar_escala(entrada, configuracao_escala_de_dict(
                    metodo, dados(metodo, polaridade=polaridade),
                ))
                self.assertEqual(len(resultado.deteccoes), 2, (metodo, polaridade))
                centros = [(d.medidas.centro_blob_x, d.medidas.centro_blob_y) for d in resultado.deteccoes]
                self.assertEqual(centros, [(32, 40), (92, 86)])
                self.assertLess(resultado.deteccoes[0].medidas.sigma_blob, resultado.deteccoes[1].medidas.sigma_blob)
                np.testing.assert_array_equal(entrada, antes)

    def test_backend_real_imagem_vazia_nao_cria_objetos(self):
        for metodo in ("log", "dog"):
            resultado = detectar_escala(np.zeros((32, 32), np.uint8), configuracao_escala_de_dict(metodo, dados(metodo)))
            self.assertEqual(resultado.deteccoes, ())


if __name__ == "__main__":
    unittest.main()
