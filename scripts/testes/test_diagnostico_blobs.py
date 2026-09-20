"""Casos geométricos sintéticos do diagnóstico de saídas salvas de blobs."""

from copy import deepcopy
import json
from math import ceil, floor, pi
import unittest

from analise.diagnostico_blobs import diagnosticar_quadro


def anotacao(indice=0, classe=0, caixa=(10, 10, 20, 20)):
    return dict(zip(
        ("indice_anotacao", "classe", "caixa_x_px", "caixa_y_px", "caixa_largura_px", "caixa_altura_px"),
        (indice, classe, *caixa),
    ))


def deteccao(indice=0, classe=0, centro=(20, 20), diametro=8, caixa=None):
    x, y = centro
    raio = diametro / 2
    if caixa is None:
        x0, y0 = max(0, floor(x - raio)), max(0, floor(y - raio))
        x1, y1 = min(100, ceil(x + raio)), min(100, ceil(y + raio))
        caixa = (x0, y0, x1 - x0, y1 - y0)
    registro = anotacao(indice, classe, caixa)
    registro["indice_deteccao"] = registro.pop("indice_anotacao")
    registro.update(centro_blob_x_px=x, centro_blob_y_px=y, diametro_blob_px=diametro,
                    area_estimada_blob_px2=pi * (raio * raio))
    return registro


class DiagnosticoGeometrico(unittest.TestCase):
    def diagnosticar(self, anotacoes, deteccoes):
        return diagnosticar_quadro(anotacoes, deteccoes, 100, 100)

    def test_centro_dentro_com_caixa_pequena_nao_e_rotulado_como_acerto(self):
        resultado = self.diagnosticar([anotacao()], [deteccao()])
        a = resultado["anotacoes"][0]
        self.assertEqual(a["indices_deteccoes"], [0])
        self.assertEqual(a["quantidade_centros"], 1)
        self.assertEqual(a["incidencias"][0]["razao_area_caixa"], 64 / 400)
        self.assertEqual(a["melhor_iou_qualquer_classe"], 64 / 400)
        self.assertEqual(resultado["deteccoes"][0]["categoria_incidencia"], "um")
        self.assertFalse({"acertos", "tp", "fp", "fn", "f1"}.intersection(resultado["resumo"]))

    def test_intervalo_inclui_esquerda_topo_e_exclui_direita_fundo(self):
        pontos = [deteccao(i, centro=p, diametro=2) for i, p in enumerate(
            ((10, 10), (30, 20), (20, 30), (29.9999, 29.9999))
        )]
        resultado = self.diagnosticar([anotacao()], pontos)
        self.assertEqual(resultado["anotacoes"][0]["indices_deteccoes"], [0, 3])
        self.assertEqual([d["quantidade_anotacoes"] for d in resultado["deteccoes"]], [1, 0, 0, 1])

    def test_usa_centro_bruto_em_vez_do_centro_da_caixa_recortada(self):
        # O centro da caixa é (2.5, 2.5), fora da anotação. O keypoint é (1, 1).
        resultado = self.diagnosticar(
            [anotacao(caixa=(0, 0, 2, 2))], [deteccao(centro=(1, 1), diametro=8)],
        )
        a, d = resultado["anotacoes"][0], resultado["deteccoes"][0]
        self.assertEqual(a["quantidade_centros"], 1)
        self.assertEqual(a["incidencias"][0]["razao_area_caixa"], 25 / 4)
        self.assertEqual(a["incidencias"][0]["iou"], 4 / 25)
        self.assertEqual((d["centro_blob_x_px"], d["centro_blob_y_px"]), (1, 1))

    def test_dois_centros_na_mesma_anotacao_sem_supressao(self):
        resultado = self.diagnosticar(
            [anotacao()], [deteccao(8, centro=(15, 15)), deteccao(3, centro=(25, 25))],
        )
        self.assertEqual(resultado["anotacoes"][0]["indices_deteccoes"], [3, 8])
        resumo = resultado["resumo"]
        self.assertEqual(resumo["quantidade_incidencias"], 2)
        self.assertEqual(resumo["anotacoes_por_quantidade_centros"], {"zero": 0, "um": 0, "multiplos": 1})
        self.assertEqual(resumo["deteccoes_por_quantidade_anotacoes"], {"zero": 0, "um": 2, "multiplos": 0})

    def test_um_centro_em_duas_anotacoes_sem_pareamento_exclusivo(self):
        resultado = self.diagnosticar(
            [anotacao(7), anotacao(2, classe=1, caixa=(20, 20, 20, 20))],
            [deteccao(centro=(25, 25))],
        )
        d = resultado["deteccoes"][0]
        self.assertEqual(d["indices_anotacoes"], [2, 7])
        self.assertEqual(d["categoria_incidencia"], "multiplos")
        self.assertEqual(resultado["resumo"]["quantidade_incidencias"], 2)
        self.assertEqual(resultado["resumo"]["anotacoes_por_quantidade_centros"]["um"], 2)

    def test_melhor_iou_examina_tambem_caixas_com_centro_fora(self):
        resultado = self.diagnosticar([anotacao()], [deteccao(centro=(31, 20), diametro=30)])
        a = resultado["anotacoes"][0]
        self.assertEqual(a["quantidade_centros"], 0)
        self.assertEqual(a["incidencias"], [])
        self.assertAlmostEqual(a["melhor_iou_qualquer_classe"], 280 / 1020)
        self.assertEqual(a["melhor_iou_mesmo_grupo"], a["melhor_iou_qualquer_classe"])

    def test_melhor_iou_geral_e_por_grupo_sao_distintos(self):
        resultado = self.diagnosticar(
            [anotacao(classe=0)], [deteccao(0, classe=1, diametro=20), deteccao(1, classe=2, diametro=10)],
        )
        a = resultado["anotacoes"][0]
        self.assertEqual(a["melhor_iou_qualquer_classe"], 1)
        self.assertEqual(a["melhor_iou_mesmo_grupo"], 0.25)
        self.assertEqual([i["mesmo_grupo"] for i in a["incidencias"]], [False, True])

    def test_classe_zero_e_dois_compartilham_grupo(self):
        for original, prevista in ((0, 2), (2, 0)):
            with self.subTest(original=original, prevista=prevista):
                resultado = self.diagnosticar([anotacao(classe=original)], [deteccao(classe=prevista)])
                a = resultado["anotacoes"][0]
                self.assertEqual(a["grupo"], "individuos")
                self.assertTrue(a["incidencias"][0]["mesmo_grupo"])
                self.assertEqual(a["melhor_iou_mesmo_grupo"], a["melhor_iou_qualquer_classe"])

    def test_sem_deteccao_no_mesmo_grupo_retorna_none(self):
        resultado = self.diagnosticar([anotacao(classe=1)], [deteccao(classe=0)])
        a = resultado["anotacoes"][0]
        self.assertEqual(a["quantidade_centros"], 1)
        self.assertIsNone(a["melhor_iou_mesmo_grupo"])
        self.assertGreater(a["melhor_iou_qualquer_classe"], 0)

    def test_deteccoes_sem_sobreposicao_retornam_zero_e_nao_none(self):
        resultado = self.diagnosticar([anotacao()], [deteccao(centro=(80, 80))])
        a = resultado["anotacoes"][0]
        self.assertEqual(a["melhor_iou_qualquer_classe"], 0.0)
        self.assertEqual(a["melhor_iou_mesmo_grupo"], 0.0)
        self.assertEqual(resultado["deteccoes"][0]["categoria_incidencia"], "zero")

    def test_ausencia_de_deteccoes_preserva_anotacoes_e_universos_vazios(self):
        resultado = self.diagnosticar([anotacao(0, 0), anotacao(1, 1), anotacao(2, 2)], [])
        self.assertEqual(resultado["deteccoes"], [])
        for a in resultado["anotacoes"]:
            self.assertEqual(a["quantidade_centros"], 0)
            self.assertIsNone(a["melhor_iou_qualquer_classe"])
            self.assertIsNone(a["melhor_iou_mesmo_grupo"])
        self.assertEqual(resultado["resumo"]["anotacoes_por_classe"], {"0": 1, "1": 1, "2": 1})
        self.assertEqual(resultado["resumo"]["anotacoes_por_quantidade_centros"]["zero"], 3)

    def test_ausencia_de_anotacoes_preserva_deteccoes(self):
        resultado = self.diagnosticar([], [deteccao(0, 0), deteccao(1, 1), deteccao(2, 2)])
        self.assertEqual(resultado["anotacoes"], [])
        for d in resultado["deteccoes"]:
            self.assertEqual(d["indices_anotacoes"], [])
            self.assertEqual(d["categoria_incidencia"], "zero")
        self.assertEqual(resultado["resumo"]["deteccoes_por_classe"], {"0": 1, "1": 1, "2": 1})
        self.assertEqual(resultado["resumo"]["quantidade_incidencias"], 0)

    def test_ambos_vazios_retornam_resumo_zerado(self):
        resultado = self.diagnosticar([], [])
        self.assertEqual(resultado["anotacoes"], [])
        self.assertEqual(resultado["deteccoes"], [])
        for valor in resultado["resumo"].values():
            self.assertTrue(all(x == 0 for x in valor.values()) if isinstance(valor, dict) else valor == 0)

    def test_incidencias_e_iou_geral_independem_dos_rotulos(self):
        anotacoes = [anotacao(0, 0), anotacao(1, 2, (20, 20, 20, 20))]
        deteccoes = [deteccao(0, 1, (25, 25)), deteccao(1, 0, (80, 80))]
        antes = self.diagnosticar(anotacoes, deteccoes)
        for registro in anotacoes + deteccoes:
            registro["classe"] = (registro["classe"] + 1) % 3
        depois = self.diagnosticar(anotacoes, deteccoes)
        for a, b in zip(antes["anotacoes"], depois["anotacoes"]):
            self.assertEqual(a["indices_deteccoes"], b["indices_deteccoes"])
            self.assertEqual(a["melhor_iou_qualquer_classe"], b["melhor_iou_qualquer_classe"])
            self.assertEqual([x["razao_area_caixa"] for x in a["incidencias"]],
                             [x["razao_area_caixa"] for x in b["incidencias"]])
        for a, b in zip(antes["deteccoes"], depois["deteccoes"]):
            self.assertEqual(a["indices_anotacoes"], b["indices_anotacoes"])

    def test_razao_usa_area_da_caixa_e_nao_area_do_disco(self):
        d = deteccao(diametro=4, caixa=(10, 10, 20, 20))
        resultado = self.diagnosticar([anotacao()], [d])
        self.assertEqual(resultado["anotacoes"][0]["incidencias"][0]["razao_area_caixa"], 1)
        self.assertEqual(resultado["deteccoes"][0]["area_estimada_blob_px2"], pi * 4)

    def test_ordenacao_deterministica_e_indices_independentes_por_lado(self):
        a = [anotacao(8), anotacao(3)]
        d = [deteccao(8), deteccao(3)]
        antes = self.diagnosticar(a, d)
        depois = self.diagnosticar(list(reversed(a)), list(reversed(d)))
        self.assertEqual(antes, depois)
        self.assertEqual([x["indice_anotacao"] for x in antes["anotacoes"]], [3, 8])
        self.assertEqual([x["indice_deteccao"] for x in antes["deteccoes"]], [3, 8])

    def test_preserva_entradas_e_medidas_originais_em_saida_serializavel(self):
        a = [anotacao()]
        d = [deteccao(centro=(20.25, 20.5), diametro=7.5)]
        d[0]["origem_medidas"] = "simpleblob_keypoint"
        antes = deepcopy((a, d))
        resultado = self.diagnosticar(a, d)
        self.assertEqual((a, d), antes)
        for campo in ("caixa_x_px", "caixa_y_px", "caixa_largura_px", "caixa_altura_px",
                      "centro_blob_x_px", "centro_blob_y_px", "diametro_blob_px", "area_estimada_blob_px2", "origem_medidas"):
            self.assertEqual(resultado["deteccoes"][0][campo], d[0][campo])
        json.loads(json.dumps(resultado, allow_nan=False))
        resultado["anotacoes"][0]["caixa_x_px"] = 99
        resultado["deteccoes"][0]["indices_anotacoes"].append(99)
        self.assertEqual((a, d), antes)

    def test_tolerancia_decimal_da_anotacao_nao_recorta_ou_desloca_caixa(self):
        resultado = self.diagnosticar([anotacao(caixa=(-1e-7, 0, 5, 5))], [deteccao(centro=(1, 1), diametro=2)])
        self.assertEqual(resultado["anotacoes"][0]["caixa_x_px"], -1e-7)
        self.assertEqual(resultado["anotacoes"][0]["quantidade_centros"], 1)


class ValidacaoDiagnostico(unittest.TestCase):
    def test_dimensoes_exigem_inteiros_positivos(self):
        for largura, altura in ((0, 100), (100, -1), (True, 100), (100, 100.0), (100, "100")):
            with self.subTest(largura=largura, altura=altura), self.assertRaises((TypeError, ValueError)):
                diagnosticar_quadro([], [], largura, altura)

    def test_colecoes_e_registros_exigem_tipos_esperados(self):
        for a, d in ((None, []), ([], ()), ([None], []), ([], [1])):
            with self.subTest(a=a, d=d), self.assertRaises(TypeError):
                diagnosticar_quadro(a, d, 100, 100)

    def test_campos_obrigatorios(self):
        for deteccoes in (False, True):
            original = deteccao() if deteccoes else anotacao()
            for campo in original:
                registro = deepcopy(original)
                del registro[campo]
                with self.subTest(deteccoes=deteccoes, campo=campo), self.assertRaises(ValueError):
                    diagnosticar_quadro([] if deteccoes else [registro], [registro] if deteccoes else [], 100, 100)

    def test_indices_duplicados_rejeitados_em_cada_lado(self):
        for a, d in (([anotacao(), anotacao()], []), ([], [deteccao(), deteccao()])):
            with self.subTest(a=a, d=d), self.assertRaisesRegex(ValueError, "repetido"):
                diagnosticar_quadro(a, d, 100, 100)

    def test_indices_e_classes_invalidos(self):
        for campo, valores in (("indice_anotacao", (-1, True, 0.0, "0")), ("classe", (-1, 3, True, "0"))):
            for valor in valores:
                registro = anotacao()
                registro[campo] = valor
                with self.subTest(campo=campo, valor=valor), self.assertRaises((TypeError, ValueError)):
                    diagnosticar_quadro([registro], [], 100, 100)

    def test_campos_reais_rejeitam_booleanos_textos_e_nao_finitos(self):
        campos = ("caixa_x_px", "caixa_y_px", "caixa_largura_px", "caixa_altura_px",
                  "centro_blob_x_px", "centro_blob_y_px", "diametro_blob_px", "area_estimada_blob_px2")
        for campo in campos:
            for valor in (True, "1", float("nan"), float("inf"), float("-inf")):
                registro = deteccao()
                registro[campo] = valor
                with self.subTest(campo=campo, valor=valor), self.assertRaises((TypeError, ValueError)):
                    diagnosticar_quadro([], [registro], 100, 100)

    def test_caixas_nao_positivas_ou_fora_da_imagem(self):
        for caixa in ((10, 10, 0, 20), (10, 10, 20, -1), (-1, 0, 20, 20),
                      (90, 90, 20, 20), (10, 10, 1e-200, 1e-200)):
            with self.subTest(caixa=caixa), self.assertRaises(ValueError):
                diagnosticar_quadro([anotacao(caixa=caixa)], [], 100, 100)

    def test_centro_bruto_fora_da_imagem_ou_da_caixa(self):
        for campo, valor in (("centro_blob_x_px", -1), ("centro_blob_x_px", 100),
                             ("centro_blob_y_px", 100), ("centro_blob_x_px", 50)):
            registro = deteccao()
            registro[campo] = valor
            with self.subTest(campo=campo, valor=valor), self.assertRaises(ValueError):
                diagnosticar_quadro([], [registro], 100, 100)

    def test_diametro_e_area_estimada_exigem_coerencia(self):
        for campo, valor in (("diametro_blob_px", 0), ("diametro_blob_px", -1),
                             ("area_estimada_blob_px2", 0), ("area_estimada_blob_px2", 50)):
            registro = deteccao()
            registro[campo] = valor
            with self.subTest(campo=campo, valor=valor), self.assertRaises(ValueError):
                diagnosticar_quadro([], [registro], 100, 100)

    def test_origem_opcional_deve_identificar_medidas_estimadas_se_presente(self):
        registro = deteccao()
        resultado = diagnosticar_quadro([], [registro], 100, 100)
        self.assertNotIn("origem_medidas", resultado["deteccoes"][0])
        for origem in (None, "pixels_segmentados", 1):
            registro["origem_medidas"] = origem
            with self.subTest(origem=origem), self.assertRaises(ValueError):
                diagnosticar_quadro([], [registro], 100, 100)


if __name__ == "__main__":
    unittest.main()
