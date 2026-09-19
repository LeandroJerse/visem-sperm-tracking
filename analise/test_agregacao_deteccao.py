"""Contratos sintéticos da agregação, sem imagens ou resultados da base."""

from copy import deepcopy
import unittest

from analise.agregacao_deteccao import agregar
from analise.avaliacao_deteccao import Objeto, avaliar


def caixa(indice, classe=0, x=0):
    return Objeto(indice, classe, x, 0, 10, 10)


class TesteAgregacao(unittest.TestCase):
    def test_soma_contagens_antes_de_calcular_f1(self):
        objetos = [caixa(classe, classe, x=20 * classe) for classe in range(3)]
        primeiro = avaliar(objetos, objetos)
        segundo = avaliar([], [caixa(i, x=20 * i) for i in range(9)])
        resultado = agregar([primeiro, segundo])
        principal = resultado["principal"]
        self.assertEqual(resultado["quantidade_quadros"], 2)
        self.assertEqual(principal["totais"], {"tp": 3, "fp": 9, "fn": 0})
        self.assertAlmostEqual(principal["por_classe"]["0"]["f1"], 2 / 11)
        media_f1_quadros = (
            primeiro["principal"]["por_classe"]["0"]["f1"]
            + segundo["principal"]["por_classe"]["0"]["f1"]
        ) / 2
        self.assertNotEqual(principal["por_classe"]["0"]["f1"], media_f1_quadros)
        self.assertAlmostEqual(principal["macro_f1"], (2 / 11 + 1 + 1) / 3)

    def test_classes_sem_casos_por_quadro_podem_ter_macro_no_conjunto(self):
        resultados = [avaliar([caixa(0, classe)], [caixa(0, classe)])
                      for classe in range(3)]
        for resultado in resultados:
            self.assertIsNone(resultado["principal"]["macro_f1"])
        agregado = agregar(iter(resultados))
        self.assertEqual(agregado["principal"]["macro_f1"], 1.0)
        self.assertEqual(agregado["principal"]["situacao_macro_f1"], "definido")

    def test_sem_casos_permanece_indefinido_e_previsoes_dao_zero(self):
        agregado = agregar([avaliar([], []), avaliar([], [caixa(0, classe=1)])])
        principal = agregado["principal"]
        self.assertIsNone(principal["por_classe"]["0"]["f1"])
        self.assertEqual(principal["por_classe"]["0"]["situacao_f1"], "sem_casos")
        self.assertEqual(principal["por_classe"]["1"]["f1"], 0.0)
        self.assertIsNone(principal["macro_f1"])
        self.assertEqual(principal["situacao_macro_f1"], "classes_sem_casos")
        self.assertEqual(agregado["localizacao"]["metricas"]["f1"], 0.0)

    def test_preserva_localizacao_independente_do_matching_principal(self):
        # Os dois pares principais são corretos por classe, mas a localização
        # escolhe outros pares com maior IoU, ambos com classes diferentes.
        primeiro = avaliar(
            [caixa(0, classe=0, x=0), caixa(1, classe=1, x=2)],
            [caixa(0, classe=0, x=1.5), caixa(1, classe=1, x=0.5)],
        )
        segundo = avaliar(
            [caixa(0, classe=2), caixa(1, classe=2, x=40)],
            [caixa(0, classe=2), caixa(1, classe=2, x=80)],
        )
        agregado = agregar([primeiro, segundo])
        self.assertEqual(agregado["principal"]["totais"], {"tp": 3, "fp": 1, "fn": 1})
        localizacao = agregado["localizacao"]
        self.assertEqual(localizacao["matriz_confusao_pares"], [
            [0, 1, 0], [1, 0, 0], [0, 0, 1],
        ])
        self.assertEqual(localizacao["pares_com_classe_correta"], 1)
        self.assertEqual(localizacao["pares_com_classe_incorreta"], 2)
        self.assertEqual(localizacao["metricas"]["f1"], 0.75)

    def test_rejeita_conjunto_vazio_mas_aceita_quadro_vazio(self):
        with self.assertRaisesRegex(ValueError, "pelo menos uma"):
            agregar(iter(()))
        agregado = agregar([avaliar([], [])])
        self.assertEqual(agregado["quantidade_quadros"], 1)
        self.assertIsNone(agregado["localizacao"]["metricas"]["f1"])

    def test_nao_modifica_origens_nem_compartilha_matriz_ou_criterios(self):
        resultados = [avaliar([caixa(0)], [caixa(0)])]
        original = deepcopy(resultados)
        agregado = agregar(resultados)
        agregado["localizacao"]["matriz_confusao_pares"][0][0] = 999
        agregado["criterios"]["limiar_iou"] = 0.9
        self.assertEqual(resultados, original)

    def test_rejeita_criterios_diferentes(self):
        primeiro = avaliar([], [])
        segundo = deepcopy(primeiro)
        segundo["criterios"]["limiar_iou"] = 0.7
        with self.assertRaisesRegex(ValueError, "critérios"):
            agregar([primeiro, segundo])

    def test_rejeita_contagens_invalidas_e_matriz_inconsistente(self):
        for valor, excecao in ((True, TypeError), (1.5, TypeError), (-1, ValueError)):
            resultado = avaliar([], [])
            resultado["principal"]["por_classe"]["0"]["tp"] = valor
            with self.subTest(valor=valor), self.assertRaises(excecao):
                agregar([resultado])
        resultado = avaliar([], [])
        resultado["localizacao"]["matriz_confusao_pares"][0][1] = 1
        with self.assertRaisesRegex(ValueError, "matriz de confusão"):
            agregar([resultado])


if __name__ == "__main__":
    unittest.main()
