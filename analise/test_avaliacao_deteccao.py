"""Contratos sintéticos do avaliador; não usam imagens ou resultados da base."""

from dataclasses import FrozenInstanceError
import unittest

from analise.avaliacao_deteccao import Objeto, avaliar, iou


def caixa(indice, classe=0, x=0, y=0, largura=10, altura=10):
    return Objeto(indice, classe, x, y, largura, altura)


class TesteObjetoEIoU(unittest.TestCase):
    def test_objeto_nao_pode_ser_alterado(self):
        objeto = caixa(0)
        with self.assertRaises(FrozenInstanceError):
            objeto.classe = 1

    def test_rejeita_campos_invalidos(self):
        casos = (
            ({"indice": -1}, ValueError),
            ({"indice": True}, TypeError),
            ({"classe": 3}, ValueError),
            ({"classe": False}, TypeError),
            ({"x": float("nan")}, ValueError),
            ({"y": "0"}, TypeError),
            ({"largura": 0}, ValueError),
            ({"altura": -1}, ValueError),
            ({"altura": float("inf")}, ValueError),
        )
        for campos, excecao in casos:
            argumentos = {"indice": 0, **campos}
            with self.subTest(campos=campos), self.assertRaises(excecao):
                caixa(**argumentos)

    def test_iou_identica_disjunta_e_borda(self):
        self.assertEqual(iou(caixa(0), caixa(1)), 1.0)
        self.assertEqual(iou(caixa(0), caixa(1, x=20)), 0.0)
        self.assertEqual(iou(caixa(0), caixa(1, x=10)), 0.0)

    def test_iou_fracionaria_e_simetrica(self):
        a = caixa(0, x=0.5)
        b = caixa(1, x=2)
        self.assertAlmostEqual(iou(a, b), 8.5 / 11.5)
        self.assertEqual(iou(a, b), iou(b, a))


class TesteAvaliacao(unittest.TestCase):
    def test_acertos_perfeitos_nas_tres_classes(self):
        anotacoes = [caixa(i, classe=i, x=20 * i) for i in range(3)]
        deteccoes = [caixa(i + 10, classe=i, x=20 * i) for i in range(3)]
        resultado = avaliar(anotacoes, deteccoes)
        principal = resultado["principal"]
        self.assertEqual(principal["totais"], {"tp": 3, "fp": 0, "fn": 0})
        self.assertEqual(principal["macro_f1"], 1.0)
        self.assertEqual(principal["situacao_macro_f1"], "definido")
        for classe in ("0", "1", "2"):
            self.assertEqual(principal["por_classe"][classe], {
                "tp": 1, "fp": 0, "fn": 0,
                "precisao": 1.0, "recall": 1.0, "f1": 1.0,
                "situacao_f1": "definido",
            })
        self.assertEqual(principal["anotacoes_sem_par"], [])
        self.assertEqual(principal["deteccoes_sem_par"], [])
        self.assertEqual(resultado["localizacao"]["matriz_confusao_pares"], [
            [1, 0, 0], [0, 1, 0], [0, 0, 1],
        ])

    def test_classe_errada_so_forma_par_na_localizacao(self):
        resultado = avaliar([caixa(7, classe=0)], [caixa(9, classe=1)])
        principal = resultado["principal"]
        localizacao = resultado["localizacao"]
        self.assertEqual(principal["totais"], {"tp": 0, "fp": 1, "fn": 1})
        self.assertEqual(principal["pares"], [])
        self.assertEqual(principal["anotacoes_sem_par"], [7])
        self.assertEqual(principal["deteccoes_sem_par"], [9])
        self.assertEqual(principal["por_classe"]["0"]["f1"], 0.0)
        self.assertEqual(principal["por_classe"]["1"]["f1"], 0.0)
        self.assertEqual(localizacao["metricas"]["f1"], 1.0)
        self.assertEqual(localizacao["pares_com_classe_correta"], 0)
        self.assertEqual(localizacao["pares_com_classe_incorreta"], 1)
        self.assertEqual(localizacao["matriz_confusao_pares"], [
            [0, 1, 0], [0, 0, 0], [0, 0, 0],
        ])
        self.assertEqual(localizacao["pares"][0], {
            "indice_anotacao": 7, "indice_deteccao": 9,
            "classe_anotacao": 0, "classe_deteccao": 1, "iou": 1.0,
        })

    def test_duplicata_nao_pode_contar_como_dois_acertos(self):
        resultado = avaliar([caixa(0)], [caixa(1), caixa(2)])
        principal = resultado["principal"]
        self.assertEqual(principal["totais"], {"tp": 1, "fp": 1, "fn": 0})
        self.assertEqual(len(principal["pares"]), 1)
        self.assertEqual(len(principal["deteccoes_sem_par"]), 1)
        self.assertAlmostEqual(principal["por_classe"]["0"]["f1"], 2 / 3)

    def test_pareamentos_principal_e_auxiliar_sao_independentes(self):
        # As caixas mais próximas têm classes diferentes. O diagnóstico pode
        # escolher outros pares, mas não pode modificar os dois acertos principais.
        anotacoes = [caixa(10, classe=0, x=0), caixa(20, classe=1, x=2)]
        deteccoes = [caixa(30, classe=0, x=1.5), caixa(40, classe=1, x=0.5)]
        resultado = avaliar(anotacoes, deteccoes)
        self.assertEqual(resultado["principal"]["totais"], {"tp": 2, "fp": 0, "fn": 0})
        self.assertEqual(resultado["localizacao"]["metricas"]["tp"], 2)
        self.assertEqual(resultado["localizacao"]["pares_com_classe_incorreta"], 2)
        self.assertEqual([
            (par["indice_anotacao"], par["indice_deteccao"])
            for par in resultado["principal"]["pares"]
        ], [(10, 30), (20, 40)])
        self.assertEqual([
            (par["indice_anotacao"], par["indice_deteccao"])
            for par in resultado["localizacao"]["pares"]
        ], [(10, 40), (20, 30)])

    def test_limiar_inclui_iou_exatamente_meio(self):
        resultado = avaliar([caixa(0)], [caixa(0, largura=20)])
        self.assertEqual(resultado["principal"]["totais"]["tp"], 1)
        self.assertEqual(resultado["principal"]["pares"][0]["iou"], 0.5)

    def test_iou_abaixo_do_limiar_nao_forma_par(self):
        resultado = avaliar([caixa(0)], [caixa(0, largura=21)])
        self.assertEqual(resultado["principal"]["totais"], {"tp": 0, "fp": 1, "fn": 1})
        self.assertEqual(resultado["localizacao"]["pares"], [])

    def test_ambos_vazios_nao_representam_f1_zero(self):
        resultado = avaliar([], [])
        principal = resultado["principal"]
        self.assertIsNone(principal["macro_f1"])
        self.assertEqual(principal["situacao_macro_f1"], "classes_sem_casos")
        self.assertEqual(principal["totais"], {"tp": 0, "fp": 0, "fn": 0})
        for metricas in principal["por_classe"].values():
            self.assertIsNone(metricas["precisao"])
            self.assertIsNone(metricas["recall"])
            self.assertIsNone(metricas["f1"])
            self.assertEqual(metricas["situacao_f1"], "sem_casos")
        self.assertIsNone(resultado["localizacao"]["metricas"]["f1"])
        self.assertEqual(resultado["localizacao"]["matriz_confusao_pares"], [
            [0, 0, 0], [0, 0, 0], [0, 0, 0],
        ])

    def test_somente_anotacoes_produz_falsos_negativos_e_f1_zero(self):
        resultado = avaliar([caixa(i, classe=i) for i in range(3)], [])
        principal = resultado["principal"]
        self.assertEqual(principal["totais"], {"tp": 0, "fp": 0, "fn": 3})
        self.assertEqual(principal["macro_f1"], 0.0)
        self.assertEqual(principal["anotacoes_sem_par"], [0, 1, 2])
        for metricas in principal["por_classe"].values():
            self.assertIsNone(metricas["precisao"])
            self.assertEqual(metricas["recall"], 0.0)
            self.assertEqual(metricas["f1"], 0.0)
            self.assertEqual(metricas["situacao_f1"], "definido")

    def test_somente_deteccoes_produz_falsos_positivos_e_f1_zero(self):
        resultado = avaliar([], [caixa(i, classe=i) for i in range(3)])
        principal = resultado["principal"]
        self.assertEqual(principal["totais"], {"tp": 0, "fp": 3, "fn": 0})
        self.assertEqual(principal["macro_f1"], 0.0)
        self.assertEqual(principal["deteccoes_sem_par"], [0, 1, 2])
        for metricas in principal["por_classe"].values():
            self.assertEqual(metricas["precisao"], 0.0)
            self.assertIsNone(metricas["recall"])
            self.assertEqual(metricas["f1"], 0.0)

    def test_macro_nao_exclui_classes_ausentes(self):
        resultado = avaliar([caixa(0)], [caixa(1)])
        principal = resultado["principal"]
        self.assertEqual(principal["por_classe"]["0"]["f1"], 1.0)
        self.assertIsNone(principal["por_classe"]["1"]["f1"])
        self.assertIsNone(principal["por_classe"]["2"]["f1"])
        self.assertIsNone(principal["macro_f1"])
        resultado_sem_deteccoes = avaliar([caixa(0)], [])
        self.assertEqual(resultado_sem_deteccoes["principal"]["por_classe"]["0"]["f1"], 0.0)
        self.assertIsNone(resultado_sem_deteccoes["principal"]["macro_f1"])

    def test_matching_maximo_evitaria_erro_de_greedy(self):
        # P1/A é a maior IoU isolada, mas consumiria o único par válido de P2.
        anotacoes = [caixa(10, x=2), caixa(20, x=6)]
        deteccoes = [caixa(30, x=3), caixa(40, x=0)]
        principal = avaliar(anotacoes, deteccoes)["principal"]
        self.assertEqual(principal["totais"], {"tp": 2, "fp": 0, "fn": 0})
        self.assertEqual([
            (par["indice_anotacao"], par["indice_deteccao"])
            for par in principal["pares"]
        ], [(10, 40), (20, 30)])
        self.assertAlmostEqual(principal["pares"][0]["iou"], 8 / 12)
        self.assertAlmostEqual(principal["pares"][1]["iou"], 7 / 13)

    def test_mesma_cardinalidade_prioriza_soma_das_ious(self):
        anotacoes = [caixa(10, x=0), caixa(20, x=2)]
        deteccoes = [caixa(30, x=0.5), caixa(40, x=1.5)]
        principal = avaliar(anotacoes, deteccoes)["principal"]
        self.assertEqual([
            (par["indice_anotacao"], par["indice_deteccao"])
            for par in principal["pares"]
        ], [(10, 30), (20, 40)])
        self.assertAlmostEqual(sum(par["iou"] for par in principal["pares"]), 19 / 10.5)

    def test_ordem_de_entrada_nao_muda_o_resultado(self):
        anotacoes = [caixa(10, x=0), caixa(20, x=2)]
        deteccoes = [caixa(30, x=0.5), caixa(40, x=1.5)]
        self.assertEqual(
            avaliar(anotacoes, deteccoes),
            avaliar(reversed(anotacoes), reversed(deteccoes)),
        )

    def test_rejeita_indices_duplicados_em_cada_lado(self):
        for anotacoes, deteccoes in (
            ([caixa(0), caixa(0, x=20)], []),
            ([], [caixa(0), caixa(0, x=20)]),
        ):
            with self.subTest(anotacoes=anotacoes, deteccoes=deteccoes):
                with self.assertRaisesRegex(ValueError, "Índice duplicado"):
                    avaliar(anotacoes, deteccoes)

    def test_rejeita_item_que_nao_e_objeto(self):
        with self.assertRaises(TypeError):
            avaliar(["caixa"], [])


if __name__ == "__main__":
    unittest.main()
