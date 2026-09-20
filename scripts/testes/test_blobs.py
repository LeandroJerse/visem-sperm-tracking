"""Contratos sintéticos do detector de blobs, com backend de detecção simulado."""

from copy import deepcopy
from dataclasses import asdict
import json
from math import pi
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from algoritmos.classicos import blobs
from algoritmos.classicos.classificacao import ConfiguracaoAreaEstimada
from algoritmos.classicos.comum import ClasseObjeto, MedidasBlob


def configuracao(**alteracoes):
    dados = {
        "polaridade": "claro",
        "limiar_minimo": 10.0,
        "limiar_maximo": 250.0,
        "passo_limiar": 10.0,
        "repetibilidade_minima": 2,
        "distancia_minima": 3.0,
        "area_minima": 3.0,
        "area_maxima": 5000.0,
        "circularidade_minima": None,
        "inercia_minima": None,
        "convexidade_minima": None,
        "classificacao": ConfiguracaoAreaEstimada(pi * 4**2, pi * 12**2),
    }
    dados.update(alteracoes)
    return blobs.ConfiguracaoBlobs(**dados)


def ponto(x=10.0, y=10.0, diametro=4.0):
    return SimpleNamespace(pt=(x, y), size=diametro)


def parametros_simulados():
    nomes = (
        "minThreshold", "maxThreshold", "thresholdStep", "minRepeatability",
        "minDistBetweenBlobs", "filterByColor", "blobColor", "filterByArea",
        "minArea", "maxArea", "collectContours", "filterByCircularity",
        "minCircularity", "maxCircularity", "filterByInertia", "minInertiaRatio",
        "maxInertiaRatio", "filterByConvexity", "minConvexity", "maxConvexity",
    )
    return SimpleNamespace(**dict.fromkeys(nomes))


class ConfiguracaoTest(unittest.TestCase):
    def test_roundtrip_json_preserva_valores_informados(self):
        original = configuracao(distancia_minima=0.1)
        dados = json.loads(json.dumps(asdict(original)))
        copia = deepcopy(dados)
        self.assertEqual(blobs.configuracao_de_dict(dados), original)
        self.assertEqual(dados, copia)
        self.assertEqual(original.distancia_minima, 0.1)
        efetivos = blobs.parametros_opencv(original)
        self.assertEqual(efetivos["minDistBetweenBlobs"], 0.10000000149011612)

    def test_parser_exige_todos_os_campos(self):
        for nome in asdict(configuracao()):
            with self.subTest(nome=nome):
                dados = asdict(configuracao())
                del dados[nome]
                with self.assertRaises(ValueError):
                    blobs.configuracao_de_dict(dados)

    def test_parser_rejeita_campos_desconhecidos(self):
        dados = asdict(configuracao())
        dados["limiar_manual"] = 100
        with self.assertRaises(ValueError):
            blobs.configuracao_de_dict(dados)
        dados = asdict(configuracao())
        dados["classificacao"]["area_pixels"] = 10
        with self.assertRaises(ValueError):
            blobs.configuracao_de_dict(dados)

    def test_parser_rejeita_objeto_e_classificacao_invalidos(self):
        for entrada in ([], None, "{}", {1: 2}):
            with self.subTest(entrada=entrada), self.assertRaises(TypeError):
                blobs.configuracao_de_dict(entrada)
        dados = asdict(configuracao())
        dados["classificacao"] = None
        with self.assertRaises(TypeError):
            blobs.configuracao_de_dict(dados)
        dados["classificacao"] = {"area_maxima_pequeno": 10}
        with self.assertRaises(ValueError):
            blobs.configuracao_de_dict(dados)

    def test_rejeita_polaridade_e_classificador_incompativeis(self):
        with self.assertRaises(ValueError):
            configuracao(polaridade="automatico")
        with self.assertRaises(TypeError):
            configuracao(classificacao={"area_maxima_pequeno": 50})

    def test_rejeita_booleanos_textos_e_nulos_nos_reais(self):
        nomes = (
            "limiar_minimo", "limiar_maximo", "passo_limiar",
            "distancia_minima", "area_minima", "area_maxima",
        )
        for nome in nomes:
            for valor in (True, "10", None):
                with self.subTest(nome=nome, valor=valor), self.assertRaises(TypeError):
                    configuracao(**{nome: valor})

    def test_rejeita_nao_finitos(self):
        nomes = (
            "limiar_minimo", "limiar_maximo", "passo_limiar", "distancia_minima",
            "area_minima", "area_maxima", "circularidade_minima", "inercia_minima",
            "convexidade_minima",
        )
        for nome in nomes:
            for valor in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(nome=nome, valor=valor), self.assertRaises(ValueError):
                    configuracao(**{nome: valor})

    def test_rejeita_overflow_e_underflow_float32(self):
        for alteracoes in (
            {"area_maxima": 1e100}, {"area_minima": 1e-100},
            {"distancia_minima": 1e-100}, {"passo_limiar": 1e-100},
            {"circularidade_minima": 1e-100},
        ):
            with self.subTest(alteracoes=alteracoes), self.assertRaises(ValueError):
                configuracao(**alteracoes)

    def test_rejeita_intervalos_colapsados_em_float32(self):
        for alteracoes in (
            {"limiar_minimo": 100.0, "limiar_maximo": 100.000001},
            {"area_minima": 5000.0, "area_maxima": 5000.00001},
        ):
            with self.subTest(alteracoes=alteracoes), self.assertRaises(ValueError):
                configuracao(**alteracoes)

    def test_rejeita_intervalos_limites_e_distancia_invalidos(self):
        for alteracoes in (
            {"limiar_minimo": -1}, {"limiar_maximo": 256},
            {"limiar_minimo": 250}, {"passo_limiar": 0},
            {"distancia_minima": 0}, {"distancia_minima": -1},
            {"area_minima": 0}, {"area_minima": 5000}, {"area_maxima": -1},
        ):
            with self.subTest(alteracoes=alteracoes), self.assertRaises(ValueError):
                configuracao(**alteracoes)

    def test_rejeita_passo_abaixo_de_um_mesmo_se_arredondar_para_um(self):
        for passo in (0.1, 1e-20, 0.9999999999):
            with self.subTest(passo=passo), self.assertRaises(ValueError):
                configuracao(passo_limiar=passo)

    def test_contagem_respeita_maximo_exclusivo(self):
        self.assertEqual(blobs.quantidade_limiares(configuracao()), 24)
        self.assertEqual(blobs.quantidade_limiares(configuracao(limiar_maximo=249)), 24)
        self.assertEqual(blobs.quantidade_limiares(configuracao(limiar_maximo=251)), 25)
        self.assertEqual(blobs.quantidade_limiares(configuracao(
            limiar_minimo=0, limiar_maximo=255, passo_limiar=1,
        )), 255)

    def test_contagem_usa_passo_efetivo_float32(self):
        config = configuracao(limiar_minimo=0, limiar_maximo=11, passo_limiar=1.1)
        self.assertEqual(blobs.quantidade_limiares(config), 10)
        self.assertEqual(blobs.parametros_opencv(config)["thresholdStep"], 1.100000023841858)

    def test_rejeita_faixa_de_apenas_um_limiar(self):
        for passo in (240, 300):
            with self.subTest(passo=passo), self.assertRaises(ValueError):
                configuracao(passo_limiar=passo, repetibilidade_minima=1)

    def test_repetibilidade_e_inteira_e_compativel_com_faixa(self):
        self.assertEqual(configuracao(repetibilidade_minima=24).repetibilidade_minima, 24)
        for valor in (True, 2.0, "2"):
            with self.subTest(valor=valor), self.assertRaises(TypeError):
                configuracao(repetibilidade_minima=valor)
        for valor in (0, -1, 25):
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                configuracao(repetibilidade_minima=valor)

    def test_forma_exige_minimo_positivo_ate_um(self):
        for nome in ("circularidade_minima", "inercia_minima", "convexidade_minima"):
            for valor in (0, -0.1, 1.0001):
                with self.subTest(nome=nome, valor=valor), self.assertRaises(ValueError):
                    configuracao(**{nome: valor})
            with self.subTest(nome=nome), self.assertRaises(TypeError):
                configuracao(**{nome: True})

    def test_parametros_explicitos_incluem_limites_de_forma_desativada(self):
        parametros = blobs.parametros_opencv(configuracao())
        self.assertEqual(len(parametros), 20)
        self.assertIs(parametros["filterByColor"], True)
        self.assertIs(parametros["filterByArea"], True)
        self.assertIs(parametros["collectContours"], False)
        self.assertEqual(parametros["blobColor"], 255)
        self.assertEqual(parametros["minArea"], 3)
        self.assertEqual(parametros["maxArea"], 5000)
        for flag, sufixo in (
            ("Circularity", "Circularity"), ("Inertia", "InertiaRatio"),
            ("Convexity", "Convexity"),
        ):
            self.assertIs(parametros[f"filterBy{flag}"], False)
            self.assertEqual(parametros[f"min{sufixo}"], 1)
            self.assertGreater(parametros[f"max{sufixo}"], 1)
        json.dumps(parametros, allow_nan=False)

    def test_forma_aceita_um_sem_exclui_lo_pelo_maximo(self):
        parametros = blobs.parametros_opencv(configuracao(
            polaridade="escuro", circularidade_minima=1,
            inercia_minima=1, convexidade_minima=1,
        ))
        self.assertEqual(parametros["blobColor"], 0)
        for flag, sufixo in (
            ("Circularity", "Circularity"), ("Inertia", "InertiaRatio"),
            ("Convexity", "Convexity"),
        ):
            self.assertIs(parametros[f"filterBy{flag}"], True)
            self.assertEqual(parametros[f"min{sufixo}"], 1)
            self.assertEqual(parametros[f"max{sufixo}"], blobs.FLOAT32_MAX)


class DeteccaoTest(unittest.TestCase):
    def simular(self, pontos=(), *, imagem=None, config=None, efeito=None):
        if imagem is None:
            imagem = np.zeros((64, 64), dtype=np.uint8)
        if config is None:
            config = configuracao()
        parametros = parametros_simulados()
        backend = Mock()
        backend.detect.return_value = tuple(pontos)
        if efeito is not None:
            backend.detect.side_effect = efeito
        with (
            patch.object(blobs.cv2, "SimpleBlobDetector_Params", return_value=parametros),
            patch.object(blobs.cv2, "SimpleBlobDetector_create", return_value=backend) as fabrica,
        ):
            resultado = blobs.detectar(imagem, config)
        fabrica.assert_called_once_with(parametros)
        backend.detect.assert_called_once()
        return resultado, parametros, backend

    def test_sem_deteccoes_preserva_dimensoes_e_ausencia_de_limiar_unico(self):
        resultado, _, _ = self.simular(imagem=np.zeros((12, 20), dtype=np.uint8))
        self.assertEqual((resultado.largura_imagem, resultado.altura_imagem), (20, 12))
        self.assertEqual(resultado.algoritmo, "blobs")
        self.assertEqual(resultado.deteccoes, ())
        self.assertEqual(resultado.registros(), ())
        self.assertEqual(resultado.linhas_yolo(), ())
        self.assertIsNone(resultado.limiar_utilizado)

    def test_caixa_fracionaria_usa_floor_ceil(self):
        resultado, _, _ = self.simular([ponto(10.25, 8.75, 5.5)])
        deteccao = resultado.deteccoes[0]
        self.assertEqual(asdict(deteccao.caixa), {"x": 7, "y": 6, "largura": 6, "altura": 6})
        self.assertIsInstance(deteccao.medidas, MedidasBlob)
        self.assertEqual(deteccao.medidas.centro_blob_x, 10.25)
        self.assertEqual(deteccao.medidas.centro_blob_y, 8.75)
        self.assertEqual(deteccao.medidas.area_estimada_blob, pi * (5.5 / 2)**2)
        self.assertFalse(deteccao.medidas.caixa_recortada_na_borda)

    def test_recorta_quatro_bordas_sem_alterar_area_estimada(self):
        imagem = np.zeros((10, 20), dtype=np.uint8)
        for x, y, caixa in (
            (0, 0, (0, 0, 5, 5)), (19, 0, (14, 0, 6, 5)),
            (0, 9, (0, 4, 5, 6)), (19, 9, (14, 4, 6, 6)),
        ):
            with self.subTest(x=x, y=y):
                resultado, _, _ = self.simular([ponto(x, y, 10)], imagem=imagem)
                deteccao = resultado.deteccoes[0]
                self.assertEqual(tuple(asdict(deteccao.caixa).values()), caixa)
                self.assertEqual(deteccao.medidas.area_estimada_blob, pi * 5**2)
                self.assertTrue(deteccao.medidas.caixa_recortada_na_borda)

    def test_area_estimada_pode_exceder_area_da_caixa_na_borda(self):
        resultado, _, _ = self.simular([ponto(1, 1, 8)])
        medidas = resultado.deteccoes[0].medidas
        self.assertEqual(medidas.area_caixa, 25)
        self.assertGreater(medidas.area_estimada_blob, medidas.area_caixa)
        self.assertEqual(medidas.centro_blob_x, 1)
        self.assertNotEqual(resultado.deteccoes[0].caixa.normalizada(64, 64)[0], 1 / 64)

    def test_classifica_tres_classes_por_area_estimada(self):
        resultado, _, _ = self.simular([ponto(32, 32, d) for d in (8, 12, 24)])
        classes = {det.medidas.diametro_blob: det.classe for det in resultado.deteccoes}
        self.assertEqual(classes, {8: ClasseObjeto.PEQUENO, 12: ClasseObjeto.NORMAL, 24: ClasseObjeto.AGLOMERADO})

    def test_classificacao_nao_recebe_area_arredondada_ou_area_da_caixa(self):
        config = configuracao(classificacao=ConfiguracaoAreaEstimada(3.5, 5.5))
        resultado, _, _ = self.simular([ponto(10, 10, 2)], config=config)
        deteccao = resultado.deteccoes[0]
        self.assertEqual(deteccao.medidas.area_caixa, 4)
        self.assertEqual(deteccao.medidas.area_estimada_blob, pi)
        self.assertEqual(deteccao.classe, ClasseObjeto.PEQUENO)

    def test_limites_de_classe_nao_alteram_caixas(self):
        primeiro, _, _ = self.simular([ponto(20, 20, 8)])
        config = configuracao(classificacao=ConfiguracaoAreaEstimada(10, 40))
        segundo, _, _ = self.simular([ponto(20, 20, 8)], config=config)
        self.assertEqual(primeiro.deteccoes[0].caixa, segundo.deteccoes[0].caixa)
        self.assertEqual(primeiro.deteccoes[0].medidas, segundo.deteccoes[0].medidas)
        self.assertNotEqual(primeiro.deteccoes[0].classe, segundo.deteccoes[0].classe)

    def test_area_estimada_nao_e_filtrada_como_area_interna(self):
        resultado, parametros, _ = self.simular([ponto(32, 32, 100)])
        self.assertEqual(parametros.maxArea, 5000)
        self.assertEqual(len(resultado.deteccoes), 1)
        self.assertGreater(resultado.deteccoes[0].medidas.area_estimada_blob, 5000)

    def test_ordena_deterministicamente_keypoints_com_mesma_caixa(self):
        pontos = [ponto(10.4, 10.4, 4), ponto(10.2, 10.2, 4), ponto(30, 3, 2)]
        primeiro, _, _ = self.simular(pontos)
        segundo, _, _ = self.simular(list(reversed(pontos)))
        self.assertEqual(primeiro, segundo)
        self.assertEqual([d.medidas.centro_blob_y for d in primeiro.deteccoes], [3, 10.2, 10.4])

    def test_nao_descarta_keypoints_duplicados_sem_regra_de_supressao(self):
        resultado, _, _ = self.simular([ponto(), ponto()])
        self.assertEqual(len(resultado.deteccoes), 2)

    def test_rejeita_keypoints_invalidos_sem_fabricar_geometria(self):
        invalidos = (
            ponto(float("nan"), 10, 4), ponto(10, float("inf"), 4),
            ponto(-1, 10, 4), ponto(64, 10, 4), ponto(10, 64, 4),
            ponto(10, 10, 0), ponto(10, 10, -1), ponto(10, 10, float("inf")),
            ponto(10, 10, 1e308), ponto(10, 10, 1e-200), ponto(True, 10, 4),
            SimpleNamespace(pt=(1, 2, 3), size=4), SimpleNamespace(pt=(1, 2)),
        )
        for keypoint in invalidos:
            with self.subTest(keypoint=keypoint), self.assertRaises((TypeError, ValueError)):
                self.simular([keypoint])

    def test_rejeita_caixa_degenerada_por_diametro_irrepresentavel_no_centro(self):
        with self.assertRaisesRegex(ValueError, "dimensões positivas"):
            self.simular([ponto(10, 10, 1e-20)])

    def test_preserva_entrada_cinza_mesmo_se_backend_a_alterar(self):
        imagem = np.arange(120, dtype=np.uint8).reshape(10, 12)[:, ::2]
        antes = imagem.copy()

        def alterar(cinza):
            self.assertTrue(cinza.flags.c_contiguous)
            self.assertFalse(np.shares_memory(cinza, imagem))
            cinza[:] = 0
            return ()

        self.simular(imagem=imagem, efeito=alterar)
        np.testing.assert_array_equal(imagem, antes)

    def test_converte_bgr_com_entrada_preservada(self):
        imagem = np.full((10, 12, 3), 42, dtype=np.uint8)
        antes = imagem.copy()
        cinza = np.full((10, 12), 17, dtype=np.uint8)

        def converter(copia, codigo):
            self.assertEqual(codigo, blobs.cv2.COLOR_BGR2GRAY)
            self.assertFalse(np.shares_memory(copia, imagem))
            copia[:] = 0
            return cinza

        with patch.object(blobs.cv2, "cvtColor", side_effect=converter) as conversor:
            _, _, backend = self.simular(imagem=imagem)
        conversor.assert_called_once()
        self.assertIs(backend.detect.call_args.args[0], cinza)
        np.testing.assert_array_equal(imagem, antes)

    def test_rejeita_entrada_invalida_antes_de_criar_detector(self):
        imagens = (
            None, [[0]], np.zeros((0, 5), dtype=np.uint8),
            np.zeros((5, 5), dtype=np.float32), np.zeros((5, 5, 4), dtype=np.uint8),
            np.zeros((5, 5, 1), dtype=np.uint8), np.zeros((5,), dtype=np.uint8),
        )
        for imagem in imagens:
            with (
                self.subTest(imagem=type(imagem)),
                patch.object(blobs.cv2, "SimpleBlobDetector_create") as fabrica,
            ):
                with self.assertRaises((TypeError, ValueError)):
                    blobs.detectar(imagem, configuracao())
                fabrica.assert_not_called()

    def test_rejeita_configuracao_errada(self):
        with self.assertRaises(TypeError):
            blobs.detectar(np.zeros((10, 10), dtype=np.uint8), {})

    def test_backend_recebe_todos_os_valores_explicitos(self):
        config = configuracao(polaridade="escuro", circularidade_minima=0.5)
        _, parametros, _ = self.simular(config=config)
        self.assertEqual(vars(parametros), blobs.parametros_opencv(config))

    def test_backend_sem_collect_contours_falha_sem_fallback(self):
        parametros = parametros_simulados()
        del parametros.collectContours
        with (
            patch.object(blobs.cv2, "SimpleBlobDetector_Params", return_value=parametros),
            patch.object(blobs.cv2, "SimpleBlobDetector_create") as fabrica,
        ):
            with self.assertRaisesRegex(RuntimeError, "collectContours"):
                blobs.detectar(np.zeros((10, 10), dtype=np.uint8), configuracao())
            fabrica.assert_not_called()

    def test_registros_e_yolo_roundtrip_sem_medidas_de_regiao_inventadas(self):
        resultado, _, _ = self.simular([ponto(1, 1, 8)])
        registros = json.loads(json.dumps(resultado.registros(), allow_nan=False))
        registro = registros[0]
        for nome in ("area_pixels", "centroide_x_px", "centroide_y_px", "ocupacao_caixa", "intensidade_media"):
            self.assertIsNone(registro[nome])
        self.assertEqual(registro["centro_blob_x_px"], 1)
        self.assertEqual(registro["centro_blob_y_px"], 1)
        self.assertEqual(registro["diametro_blob_px"], 8)
        self.assertEqual(registro["area_estimada_blob_px2"], pi * 4**2)
        self.assertTrue(registro["caixa_recortada_na_borda"])
        self.assertTrue(registro["origem_medidas"])
        classe, *coordenadas = resultado.linhas_yolo()[0].split()
        self.assertEqual(int(classe), ClasseObjeto.PEQUENO)
        valores = [float(valor) for valor in coordenadas]
        self.assertEqual(valores, [2.5 / 64, 2.5 / 64, 5 / 64, 5 / 64])


if __name__ == "__main__":
    unittest.main()
