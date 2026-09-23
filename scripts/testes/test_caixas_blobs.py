"""Testes da conversão de caixas, sem OpenCV, imagens, arquivos ou detecção."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, replace
import json
from math import ceil, floor, pi
import unittest

from algoritmos.classicos.caixas_blobs import (
    ConfiguracaoCaixaBlobs, adaptar_caixas, configuracao_caixa_de_dict, configuracao_canonica,
)
from algoritmos.classicos.comum import (
    Caixa, ClasseObjeto, Deteccao, MedidasBlob, MedidasObjeto, ResultadoDeteccao,
)


def objeto(cx=20.0, cy=30.0, diametro=6.0, classe=ClasseObjeto.NORMAL, largura=100, altura=100):
    raio = diametro / 2
    original = (floor(cx - raio), floor(cy - raio), ceil(cx + raio), ceil(cy + raio))
    x0, y0, x1, y1 = (max(0, original[0]), max(0, original[1]),
                      min(largura, original[2]), min(altura, original[3]))
    caixa = Caixa(x0, y0, x1 - x0, y1 - y0)
    medidas = MedidasBlob(cx, cy, diametro, pi * raio**2, caixa.largura * caixa.altura,
                         original != (x0, y0, x1, y1))
    return Deteccao(classe, caixa, medidas)


def resultado(*deteccoes, largura=100, altura=100):
    return ResultadoDeteccao("blobs", largura, altura, tuple(deteccoes), None)


class ConfiguracaoCaixaTest(unittest.TestCase):
    def test_modos_validos_e_canonicos(self):
        for dados, esperado in (
            ({"modo": "original"}, {"modo": "original"}),
            ({"modo": "escala", "fator": 2}, {"modo": "escala", "fator": 2.0}),
            ({"modo": "margem", "pixels": 2.5}, {"modo": "margem", "pixels": 2.5}),
        ):
            with self.subTest(dados=dados):
                antes = deepcopy(dados)
                config = configuracao_caixa_de_dict(dados)
                self.assertEqual(configuracao_canonica(config), esperado)
                self.assertEqual(dados, antes)
                json.dumps(configuracao_canonica(config), allow_nan=False)

    def test_identidades_normalizam_para_original(self):
        for dados in ({"modo": "escala", "fator": 1}, {"modo": "escala", "fator": 1.0},
                      {"modo": "margem", "pixels": 0}, {"modo": "margem", "pixels": -0.0}):
            with self.subTest(dados=dados):
                self.assertEqual(configuracao_canonica(configuracao_caixa_de_dict(dados)), {"modo": "original"})

    def test_inteiro_e_real_equivalentes_produzem_json_canonico_igual(self):
        a = configuracao_canonica(configuracao_caixa_de_dict({"modo": "escala", "fator": 2}))
        b = configuracao_canonica(configuracao_caixa_de_dict({"modo": "escala", "fator": 2.0}))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertIsInstance(a["fator"], float)

    def test_configuracao_imutavel_e_canonico_independente(self):
        config = ConfiguracaoCaixaBlobs("escala", fator=2)
        with self.assertRaises(FrozenInstanceError):
            config.fator = 3
        canonica = configuracao_canonica(config)
        canonica["fator"] = 10
        self.assertEqual(config.fator, 2)

    def test_parser_rejeita_campos_ausentes_ou_extras(self):
        for dados in ({}, {"modo": "escala"}, {"modo": "margem"},
                      {"modo": "original", "fator": None}, {"modo": "original", "pixels": 0},
                      {"modo": "escala", "fator": 2, "pixels": 0},
                      {"modo": "margem", "pixels": 2, "fator": 1},
                      {"modo": "original", "outro": 1}):
            with self.subTest(dados=dados), self.assertRaises(ValueError):
                configuracao_caixa_de_dict(dados)

    def test_parser_rejeita_objetos_e_modos_incompativeis(self):
        for dados in (None, [], "original", {1: "original"}):
            with self.subTest(dados=dados), self.assertRaises(TypeError):
                configuracao_caixa_de_dict(dados)
        for modo in (True, None, [], "fixa", "ESCALA"):
            with self.subTest(modo=modo), self.assertRaises(ValueError):
                configuracao_caixa_de_dict({"modo": modo})

    def test_rejeita_booleanos_textos_e_nao_finitos(self):
        for modo, campo in (("escala", "fator"), ("margem", "pixels")):
            for valor in (True, False, None, "2", float("nan"), float("inf"), float("-inf"), 10**400):
                with self.subTest(modo=modo, valor=valor), self.assertRaises((TypeError, ValueError)):
                    configuracao_caixa_de_dict({"modo": modo, campo: valor})

    def test_dominios_de_escala_e_margem(self):
        for dados in ({"modo": "escala", "fator": 0}, {"modo": "escala", "fator": -1},
                      {"modo": "margem", "pixels": -0.1}):
            with self.subTest(dados=dados), self.assertRaises(ValueError):
                configuracao_caixa_de_dict(dados)
        self.assertEqual(ConfiguracaoCaixaBlobs("escala", fator=0.25).fator, 0.25)

    def test_construcao_direta_tambem_valida_campos(self):
        for kwargs in ({"modo": "original", "fator": 1}, {"modo": "original", "pixels": 1},
                       {"modo": "escala", "fator": 2, "pixels": 0},
                       {"modo": "margem", "pixels": 2, "fator": 1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ConfiguracaoCaixaBlobs(**kwargs)
        for kwargs in ({"modo": "escala"}, {"modo": "margem"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TypeError):
                ConfiguracaoCaixaBlobs(**kwargs)

    def test_canonico_exige_tipo_da_configuracao(self):
        with self.assertRaises(TypeError):
            configuracao_canonica({"modo": "original"})


class AdaptacaoCaixaTest(unittest.TestCase):
    def test_identidades_preservam_objeto_registros_e_yolo_exatos(self):
        origem = resultado(objeto(), objeto(1, 1, 8, ClasseObjeto.PEQUENO))
        registros, yolo = origem.registros(), origem.linhas_yolo()
        for config in (ConfiguracaoCaixaBlobs("original"), ConfiguracaoCaixaBlobs("escala", fator=1),
                       ConfiguracaoCaixaBlobs("margem", pixels=0)):
            with self.subTest(config=config):
                adaptado = adaptar_caixas(origem, config)
                self.assertIs(adaptado, origem)
                self.assertEqual(adaptado.registros(), registros)
                self.assertEqual(adaptado.linhas_yolo(), yolo)

    def test_escala_calcula_lado_pelo_diametro(self):
        origem = resultado(objeto())
        adaptado = adaptar_caixas(origem, ConfiguracaoCaixaBlobs("escala", fator=2))
        self.assertEqual(adaptado.deteccoes[0].caixa, Caixa(14, 24, 12, 12))
        self.assertEqual(adaptado.deteccoes[0].medidas.area_caixa, 144)
        self.assertFalse(adaptado.deteccoes[0].medidas.caixa_recortada_na_borda)

    def test_margem_acrescenta_pixels_em_cada_lado(self):
        adaptado = adaptar_caixas(resultado(objeto()), ConfiguracaoCaixaBlobs("margem", pixels=2.5))
        self.assertEqual(adaptado.deteccoes[0].caixa, Caixa(14, 24, 12, 12))

    def test_arredonda_para_fora_com_centro_e_diametro_fracionarios(self):
        adaptado = adaptar_caixas(resultado(objeto(10.25, 8.75, 5.5)), ConfiguracaoCaixaBlobs("escala", fator=1.5))
        self.assertEqual(adaptado.deteccoes[0].caixa, Caixa(6, 4, 9, 9))

    def test_nao_usa_centro_ou_dimensao_da_caixa_ja_recortada(self):
        origem = resultado(objeto(1, 1, 8))
        self.assertEqual(origem.deteccoes[0].caixa, Caixa(0, 0, 5, 5))
        adaptado = adaptar_caixas(origem, ConfiguracaoCaixaBlobs("escala", fator=2))
        self.assertEqual(adaptado.deteccoes[0].caixa, Caixa(0, 0, 9, 9))
        self.assertEqual(adaptado.deteccoes[0].medidas.centro_blob_x, 1)
        self.assertEqual(adaptado.deteccoes[0].medidas.centro_blob_y, 1)

    def test_recorta_todas_as_bordas_e_preserva_centro(self):
        for centro, esperado in (((1, 1), Caixa(0, 0, 7, 7)), ((99, 1), Caixa(93, 0, 7, 7)),
                                 ((1, 99), Caixa(0, 93, 7, 7)), ((99, 99), Caixa(93, 93, 7, 7))):
            with self.subTest(centro=centro):
                origem = resultado(objeto(*centro, diametro=4))
                d = adaptar_caixas(origem, ConfiguracaoCaixaBlobs("escala", fator=3)).deteccoes[0]
                self.assertEqual(d.caixa, esperado)
                self.assertTrue(d.medidas.caixa_recortada_na_borda)
                self.assertEqual((d.medidas.centro_blob_x, d.medidas.centro_blob_y), centro)

    def test_limite_exato_da_imagem_nao_e_recorte(self):
        origem = resultado(objeto(50, 50, 20))
        adaptado = adaptar_caixas(origem, ConfiguracaoCaixaBlobs("escala", fator=5))
        self.assertEqual(adaptado.deteccoes[0].caixa, Caixa(0, 0, 100, 100))
        self.assertFalse(adaptado.deteccoes[0].medidas.caixa_recortada_na_borda)

    def test_reducao_recalcula_flag_sem_alterar_area_bruta(self):
        origem = resultado(objeto(1, 1, 8))
        d = adaptar_caixas(origem, ConfiguracaoCaixaBlobs("escala", fator=0.25)).deteccoes[0]
        self.assertEqual(d.caixa, Caixa(0, 0, 2, 2))
        self.assertFalse(d.medidas.caixa_recortada_na_borda)
        self.assertEqual(d.medidas.area_estimada_blob, pi * 16)
        self.assertGreater(d.medidas.area_estimada_blob, d.medidas.area_caixa)

    def test_preserva_classes_ordem_e_indices_locais(self):
        origem = resultado(objeto(80, 80, 30, ClasseObjeto.AGLOMERADO),
                           objeto(20, 20, 2, ClasseObjeto.PEQUENO),
                           objeto(50, 10, 10, ClasseObjeto.NORMAL))
        adaptado = adaptar_caixas(origem, ConfiguracaoCaixaBlobs("margem", pixels=10))
        self.assertEqual([d.classe for d in adaptado.deteccoes], [ClasseObjeto.AGLOMERADO, ClasseObjeto.PEQUENO, ClasseObjeto.NORMAL])
        self.assertEqual([r["indice_deteccao"] for r in adaptado.registros()], [0, 1, 2])
        for anterior, posterior in zip(origem.deteccoes, adaptado.deteccoes):
            for campo in ("centro_blob_x", "centro_blob_y", "diametro_blob", "area_estimada_blob"):
                self.assertEqual(getattr(anterior.medidas, campo), getattr(posterior.medidas, campo))

    def test_expandir_pequeno_nao_o_reclassifica_nem_aumenta_area_estimada(self):
        origem = resultado(objeto(50, 50, 2, ClasseObjeto.PEQUENO))
        d = adaptar_caixas(origem, ConfiguracaoCaixaBlobs("escala", fator=20)).deteccoes[0]
        self.assertEqual(d.classe, ClasseObjeto.PEQUENO)
        self.assertEqual(d.medidas.diametro_blob, 2)
        self.assertEqual(d.medidas.area_estimada_blob, pi)
        self.assertEqual(d.medidas.area_caixa, 1600)

    def test_transformacoes_nao_se_acumulam_sobre_caixa_anterior(self):
        origem = resultado(objeto(1, 1, 8))
        primeiro = adaptar_caixas(origem, ConfiguracaoCaixaBlobs("escala", fator=3))
        regra = ConfiguracaoCaixaBlobs("margem", pixels=2)
        self.assertEqual(adaptar_caixas(primeiro, regra), adaptar_caixas(origem, regra))

    def test_entrada_intacta_e_somente_campos_derivados_modificados(self):
        origem = resultado(objeto())
        antes = deepcopy(asdict(origem))
        adaptado = adaptar_caixas(origem, ConfiguracaoCaixaBlobs("escala", fator=2))
        self.assertEqual(asdict(origem), antes)
        self.assertIsNot(adaptado, origem)
        antigo, novo = origem.registros()[0], adaptado.registros()[0]
        permitidos = {"caixa_x_px", "caixa_y_px", "caixa_largura_px", "caixa_altura_px",
                      "caixa_centro_x_norm", "caixa_centro_y_norm", "caixa_largura_norm", "caixa_altura_norm",
                      "area_caixa_px2", "alongamento_caixa", "caixa_recortada_na_borda"}
        self.assertTrue({k for k in antigo if antigo[k] != novo[k]}.issubset(permitidos))
        for campo in ("area_pixels", "centroide_x_px", "centroide_y_px", "ocupacao_caixa", "intensidade_media"):
            self.assertIsNone(novo[campo])

    def test_yolo_reflete_caixa_adaptada_valida(self):
        origem = resultado(objeto(1, 1, 8, ClasseObjeto.PEQUENO))
        adaptado = adaptar_caixas(origem, ConfiguracaoCaixaBlobs("escala", fator=2))
        self.assertEqual(adaptado.linhas_yolo(), ("2 0.045 0.045 0.09 0.09",))
        self.assertEqual(adaptado.deteccoes[0].caixa.normalizada(100, 100), (0.045, 0.045, 0.09, 0.09))

    def test_sem_deteccoes_preserva_dimensoes_e_saida_vazia(self):
        origem = resultado(largura=640, altura=480)
        adaptado = adaptar_caixas(origem, ConfiguracaoCaixaBlobs("escala", fator=2))
        self.assertEqual(adaptado, origem)
        self.assertEqual(adaptado.registros(), ())
        self.assertEqual(adaptado.linhas_yolo(), ())

    def test_rejeita_tipo_de_resultado_e_configuracao(self):
        with self.assertRaises(TypeError):
            adaptar_caixas({}, ConfiguracaoCaixaBlobs("original"))
        with self.assertRaises(TypeError):
            adaptar_caixas(resultado(), {"modo": "original"})

    def test_identidade_tambem_rejeita_origem_incompativel(self):
        origem = resultado(objeto())
        for invalido in (replace(origem, algoritmo="limiarizacao"), replace(origem, limiar_utilizado=100)):
            with self.subTest(invalido=invalido), self.assertRaises(ValueError):
                adaptar_caixas(invalido, ConfiguracaoCaixaBlobs("original"))

    def test_rejeita_medidas_segmentadas_mesmo_com_nome_blobs(self):
        d = Deteccao(ClasseObjeto.NORMAL, Caixa(0, 0, 2, 2), MedidasObjeto(4, 0.5, 0.5, 4, 1, 1, 100))
        for config in (ConfiguracaoCaixaBlobs("original"), ConfiguracaoCaixaBlobs("escala", fator=2)):
            with self.subTest(config=config), self.assertRaises(TypeError):
                adaptar_caixas(resultado(d), config)

    def test_rejeita_overflow_em_escala_ou_margem(self):
        origem = resultado(objeto(diametro=20))
        for config in (ConfiguracaoCaixaBlobs("escala", fator=1e308),
                       ConfiguracaoCaixaBlobs("margem", pixels=1e308)):
            with self.subTest(config=config), self.assertRaisesRegex(ValueError, "positivo e finito"):
                adaptar_caixas(origem, config)

    def test_rejeita_underflow_ou_caixa_sem_dimensoes(self):
        origem = resultado(objeto())
        for fator in (5e-324, 1e-20):
            with self.subTest(fator=fator), self.assertRaises(ValueError):
                adaptar_caixas(origem, ConfiguracaoCaixaBlobs("escala", fator=fator))

    def test_lado_grande_finito_recorta_sem_fabricar_novas_medidas(self):
        origem = resultado(objeto())
        d = adaptar_caixas(origem, ConfiguracaoCaixaBlobs("margem", pixels=1e100)).deteccoes[0]
        self.assertEqual(d.caixa, Caixa(0, 0, 100, 100))
        self.assertTrue(d.medidas.caixa_recortada_na_borda)
        self.assertEqual(d.medidas.diametro_blob, 6)
        self.assertEqual(d.medidas.area_estimada_blob, pi * 9)


if __name__ == "__main__":
    unittest.main()
