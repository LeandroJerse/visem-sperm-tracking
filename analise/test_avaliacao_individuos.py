"""Contratos sintéticos da avaliação por grupos; não utilizam a base de dados."""

from copy import deepcopy
import json
import unittest

from analise.avaliacao_deteccao import Objeto, avaliar as avaliar_tres_classes
from analise.avaliacao_individuos import CRITERIOS, agregar, avaliar


def caixa(indice, classe=0, x=0, largura=10):
    return Objeto(indice, classe, x, 0, largura, 10)


class TesteAvaliacaoIndividuos(unittest.TestCase):
    def test_trocas_entre_zero_e_dois_localizam_mas_erram_classificacao(self):
        resultado = avaliar(
            [caixa(7, 0), caixa(8, 2, x=20), caixa(9, 1, x=40)],
            [caixa(17, 2), caixa(18, 0, x=20), caixa(19, 1, x=40)],
        )
        self.assertEqual(resultado["por_grupo"]["individuos"]["f1"], 1.0)
        self.assertEqual(resultado["por_grupo"]["aglomerados"]["f1"], 1.0)
        self.assertEqual(resultado["classificacao_individuos"], {
            "ordem_classes": [0, 2], "matriz_confusao": [[0, 1], [1, 0]],
            "pares_corretos": 0, "pares_incorretos": 2, "total": 2,
            "acuracia_condicional": 0.0,
        })
        self.assertEqual(resultado["pares"][0], {
            "indice_anotacao": 7, "indice_deteccao": 17,
            "classe_anotacao": 0, "classe_deteccao": 2, "iou": 1.0,
            "grupo": "individuos", "classe_correta": False,
        })
        self.assertTrue(resultado["pares"][2]["classe_correta"])
        for classe in ("0", "2", "1"):
            self.assertEqual(resultado["cobertura_por_classe"][classe], {
                "anotacoes": 1, "localizadas": 1, "perdidas": 0, "recall": 1.0,
            })

    def test_individuo_e_aglomerado_nao_formam_par_em_qualquer_direcao(self):
        for classe_a, classe_d in ((0, 1), (2, 1), (1, 0), (1, 2)):
            with self.subTest(anotacao=classe_a, deteccao=classe_d):
                a, d = [caixa(7, classe_a)], [caixa(9, classe_d)]
                resultado = avaliar(a, d)
                self.assertEqual(resultado["pares"], [])
                self.assertEqual(resultado["anotacoes_sem_par"], [7])
                self.assertEqual(resultado["deteccoes_sem_par"], [9])
                grupo_a = "aglomerados" if classe_a == 1 else "individuos"
                grupo_d = "aglomerados" if classe_d == 1 else "individuos"
                self.assertEqual(resultado["por_grupo"][grupo_a]["fn"], 1)
                self.assertEqual(resultado["por_grupo"][grupo_d]["fp"], 1)
                self.assertEqual(resultado["classificacao_individuos"]["total"], 0)
                self.assertEqual(avaliar_tres_classes(a, d)["localizacao"]["metricas"]["tp"], 1)

    def test_grupo_e_restricao_de_pareamento_nao_filtro_de_pares_agnosticos(self):
        anotacoes = [caixa(10, 2, x=0), caixa(20, 1, x=2)]
        deteccoes = [caixa(30, 0, x=1.5), caixa(40, 1, x=0.5)]
        resultado = avaliar(anotacoes, deteccoes)
        self.assertEqual([
            (p["indice_anotacao"], p["indice_deteccao"]) for p in resultado["pares"]
        ], [(10, 30), (20, 40)])
        self.assertEqual(resultado["por_grupo"]["individuos"]["tp"], 1)
        self.assertEqual(resultado["por_grupo"]["aglomerados"]["tp"], 1)
        agnostico = avaliar_tres_classes(anotacoes, deteccoes)["localizacao"]
        self.assertEqual([
            (p["indice_anotacao"], p["indice_deteccao"]) for p in agnostico["pares"]
        ], [(10, 40), (20, 30)])

    def test_uma_anotacao_nao_pode_ser_contada_duas_vezes(self):
        resultado = avaliar([caixa(0, 2)], [caixa(1, 0), caixa(2, 2)])
        grupo = resultado["por_grupo"]["individuos"]
        self.assertEqual((grupo["tp"], grupo["fp"], grupo["fn"]), (1, 1, 0))
        self.assertEqual(len(resultado["pares"]), 1)
        self.assertEqual(len(resultado["deteccoes_sem_par"]), 1)
        self.assertAlmostEqual(grupo["f1"], 2 / 3)

    def test_cardinalidade_precede_iou_e_classe_original(self):
        resultado = avaliar(
            [caixa(10, 0, x=2), caixa(20, 2, x=6)],
            [caixa(30, 0, x=3), caixa(40, 2, x=0)],
        )
        self.assertEqual([
            (p["indice_anotacao"], p["indice_deteccao"]) for p in resultado["pares"]
        ], [(10, 40), (20, 30)])
        self.assertEqual(resultado["por_grupo"]["individuos"]["tp"], 2)
        self.assertEqual(resultado["classificacao_individuos"]["pares_incorretos"], 2)

    def test_mesma_cardinalidade_prioriza_iou_sem_favorecer_classe(self):
        resultado = avaliar(
            [caixa(10, 0, x=0), caixa(20, 2, x=2)],
            [caixa(30, 2, x=0.5), caixa(40, 0, x=1.5)],
        )
        self.assertEqual([
            (p["indice_anotacao"], p["indice_deteccao"]) for p in resultado["pares"]
        ], [(10, 30), (20, 40)])
        self.assertEqual(resultado["classificacao_individuos"]["pares_incorretos"], 2)

    def test_iou_meio_e_inclusivo_e_valor_inferior_e_rejeitado(self):
        aceito = avaliar([caixa(0, 2)], [caixa(1, 0, largura=20)])
        rejeitado = avaliar([caixa(0, 2)], [caixa(1, 0, largura=21)])
        self.assertEqual(aceito["pares"][0]["iou"], 0.5)
        self.assertEqual(aceito["por_grupo"]["individuos"]["tp"], 1)
        self.assertEqual(rejeitado["pares"], [])
        self.assertEqual(rejeitado["por_grupo"]["individuos"]["f1"], 0.0)

    def test_sem_casos_e_diferente_de_erros_sem_acertos(self):
        vazio = avaliar([], [])
        for grupo in vazio["por_grupo"].values():
            self.assertIsNone(grupo["f1"])
            self.assertEqual(grupo["situacao_f1"], "sem_casos")
        self.assertIsNone(vazio["classificacao_individuos"]["acuracia_condicional"])
        self.assertIsNone(vazio["cobertura_por_classe"]["2"]["recall"])
        fp = avaliar([], [caixa(2, 2)])
        fn = avaliar([caixa(2, 2)], [])
        self.assertEqual(fp["por_grupo"]["individuos"]["fp"], 1)
        self.assertEqual(fn["por_grupo"]["individuos"]["fn"], 1)
        self.assertEqual(fp["por_grupo"]["individuos"]["f1"], 0.0)
        self.assertEqual(fn["por_grupo"]["individuos"]["f1"], 0.0)
        self.assertEqual(fn["cobertura_por_classe"]["2"]["recall"], 0.0)

    def test_preserva_entradas_ordem_indices_e_classes(self):
        anotacoes = [caixa(20, 2, x=20), caixa(10, 0)]
        deteccoes = [caixa(40, 0, x=20), caixa(30, 2)]
        antes = deepcopy((anotacoes, deteccoes))
        resultado = avaliar(anotacoes, deteccoes)
        self.assertEqual((anotacoes, deteccoes), antes)
        self.assertEqual(resultado, avaliar(reversed(anotacoes), reversed(deteccoes)))
        resultado["criterios"]["grupos"]["individuos"].append(1)
        self.assertEqual(CRITERIOS["grupos"]["individuos"], [0, 2])
        json.dumps(avaliar(anotacoes, deteccoes), allow_nan=False)

    def test_rejeita_indices_repetidos_e_itens_invalidos(self):
        with self.assertRaisesRegex(ValueError, "duplicado"):
            avaliar([caixa(0, 0), caixa(0, 2)], [])
        with self.assertRaisesRegex(ValueError, "duplicado"):
            avaliar([], [caixa(0, 0), caixa(0, 2)])
        with self.assertRaises(TypeError):
            avaliar(["caixa"], [])


class TesteAgregacaoIndividuos(unittest.TestCase):
    def test_soma_contagens_cobertura_e_matriz_antes_de_calcular_metricas(self):
        primeiro = avaliar([caixa(0, 2)], [caixa(1, 0)])
        segundo = avaliar([caixa(i, 2, x=20 * i) for i in range(9)], [])
        terceiro = avaliar([caixa(0, 0)], [caixa(1, 0)])
        entradas = [primeiro, segundo, terceiro]
        antes = deepcopy(entradas)
        resultado = agregar(iter(entradas))
        self.assertEqual(entradas, antes)
        self.assertEqual(resultado["quantidade_quadros"], 3)
        grupo = resultado["por_grupo"]["individuos"]
        self.assertEqual((grupo["tp"], grupo["fp"], grupo["fn"]), (2, 0, 9))
        self.assertAlmostEqual(grupo["f1"], 4 / 13)
        self.assertNotEqual(grupo["f1"], (1 + 0 + 1) / 3)
        self.assertEqual(resultado["cobertura_por_classe"]["2"], {
            "anotacoes": 10, "localizadas": 1, "perdidas": 9, "recall": 0.1,
        })
        self.assertEqual(resultado["classificacao_individuos"], {
            "ordem_classes": [0, 2], "matriz_confusao": [[1, 0], [1, 0]],
            "pares_corretos": 1, "pares_incorretos": 1, "total": 2,
            "acuracia_condicional": 0.5,
        })
        self.assertNotIn("pares", resultado)
        self.assertNotIn("anotacoes_sem_par", resultado)
        self.assertNotIn("deteccoes_sem_par", resultado)
        json.dumps(resultado, allow_nan=False)

    def test_aglomera_grupos_separados_e_aceita_quadro_vazio(self):
        resultado = agregar([
            avaliar([], []),
            avaliar([caixa(0, 1)], [caixa(1, 1), caixa(2, 2, x=20)]),
        ])
        self.assertEqual(resultado["quantidade_quadros"], 2)
        self.assertEqual(resultado["por_grupo"]["aglomerados"]["f1"], 1.0)
        self.assertEqual(resultado["por_grupo"]["individuos"]["f1"], 0.0)
        self.assertIsNone(resultado["classificacao_individuos"]["acuracia_condicional"])
        self.assertEqual(resultado["cobertura_por_classe"]["1"]["recall"], 1.0)

    def test_rejeita_sequencia_vazia_criterios_diferentes_e_contagens_corrompidas(self):
        with self.assertRaises(ValueError):
            agregar([])
        base = avaliar([caixa(0, 2)], [caixa(1, 0)])
        alteracoes = (
            (lambda r: r["criterios"].update(limiar_iou=0.4), ValueError),
            (lambda r: r["por_grupo"]["individuos"].update(fp=-1), ValueError),
            (lambda r: r["por_grupo"]["individuos"].update(tp=True), TypeError),
            (lambda r: r["cobertura_por_classe"]["2"].update(perdidas=1), ValueError),
            (lambda r: r["classificacao_individuos"].update(ordem_classes=[2, 0]), ValueError),
            (lambda r: r["classificacao_individuos"].update(total=2), ValueError),
            (lambda r: r["classificacao_individuos"].update(matriz_confusao=[[0, 1], [0, 0]]), ValueError),
        )
        for alterar, excecao in alteracoes:
            resultado = deepcopy(base)
            alterar(resultado)
            with self.subTest(alterar=alterar), self.assertRaises(excecao):
                agregar([resultado])


if __name__ == "__main__":
    unittest.main()
