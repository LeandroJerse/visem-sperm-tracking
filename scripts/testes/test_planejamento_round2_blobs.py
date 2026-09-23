"""Contrato v2, preservação do round1 e hipóteses pareadas sem detectar imagens."""

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from scripts.blobs import planejamento as p
from scripts.blobs import planejamento_round2 as r2


RAIZ = Path(__file__).resolve().parents[2]
SHA_ROUND1 = "59eba7c3ca133b45c5b581860677add18675a2458fbc65d28d267cf5883b2b69"


def serializar(plano):
    return json.dumps(plano, ensure_ascii=False, allow_nan=False).encode("utf-8")


def diferencas(a, b, prefixo=""):
    resultado = []
    for chave in set(a) | set(b):
        caminho = f"{prefixo}.{chave}" if prefixo else chave
        if chave not in a or chave not in b:
            resultado.append(caminho)
        elif isinstance(a[chave], dict) and isinstance(b[chave], dict):
            resultado.extend(diferencas(a[chave], b[chave], caminho))
        elif a[chave] != b[chave]:
            resultado.append(caminho)
    return resultado


class TestPlanejamentoRound2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.origem_bytes = (RAIZ / r2.ORIGEM_ROUND1).read_bytes()
        cls.origem = p.carregar_plano(cls.origem_bytes)
        cls.referencias = {x["id"]: x for x in cls.origem["configuracoes"]}

    def setUp(self):
        proibido = patch("cv2.SimpleBlobDetector_create", side_effect=AssertionError("Não executar detectores."))
        proibido.start()
        self.addCleanup(proibido.stop)
        self.plano = r2.gerar_round2(self.origem_bytes)

    def rejeitar(self, plano):
        with self.assertRaises((ValueError, TypeError)):
            p.carregar_plano(serializar(plano))

    def test_preserva_bytes_e_identidades_do_round1(self):
        self.assertEqual(hashlib.sha256(self.origem_bytes).hexdigest(), SHA_ROUND1)
        self.assertEqual((RAIZ / r2.ORIGEM_ROUND1).read_bytes(), self.origem_bytes)
        for antigo in self.origem["configuracoes"]:
            novo = deepcopy(antigo)
            novo.update(metodo="simpleblob", preprocessamento={"metodo": "nenhum"})
            self.assertEqual(p.hash_configuracao(novo), p.hash_configuracao(antigo))
        self.assertEqual(p.carregar_plano(self.origem_bytes), self.origem)

    def test_32_configs_178_quadros_76_distintas_e_blocos(self):
        self.assertEqual(p.carregar_plano(serializar(self.plano)), self.plano)
        self.assertEqual(self.plano["quadros"], self.origem["quadros"])
        configs = self.plano["configuracoes"]
        self.assertEqual(len(configs), 32)
        self.assertEqual(Counter(x["metodo"] for x in configs), {"simpleblob": 24, "log": 4, "dog": 4})
        self.assertEqual(Counter(x["bloco"] for x in configs), {"controle": 4, "exploracao": 28})
        self.assertEqual(Counter(x["preprocessamento"]["metodo"] for x in configs), {"nenhum": 24, "clahe": 8})
        antigos = {p.hash_configuracao(x) for x in self.origem["configuracoes"]}
        novos = {p.hash_configuracao(x) for x in configs}
        self.assertEqual(len(novos), 32)
        self.assertEqual(len(antigos & novos), 4)
        self.assertEqual(len(antigos | novos), 76)

    def test_controles_exatos_e_referencias_explicitas(self):
        for item, referencia in zip(self.plano["configuracoes"][:4], r2.REFERENCIAS):
            self.assertEqual(item["referencia"], referencia)
            self.assertEqual(item["parametros"], self.referencias[referencia]["parametros"])
            self.assertEqual(item["caixa"], self.referencias[referencia]["caixa"])
            self.assertEqual(p.hash_configuracao(item), p.hash_configuracao(self.referencias[referencia]))

    def test_cada_refinamento_altera_um_unico_campo(self):
        for item, esperado in zip(self.plano["configuracoes"][4:16], r2.REFINAMENTOS):
            referencia, secao, campo, valor = esperado
            antigo = self.referencias[referencia]
            self.assertEqual(item["referencia"], referencia)
            campos = ("parametros", "caixa")
            self.assertEqual(diferencas({k: item[k] for k in campos}, {k: antigo[k] for k in campos}),
                             [f"{secao}.{campo}"])
            self.assertEqual(item[secao][campo], valor)
            self.assertEqual(item["preprocessamento"], {"metodo": "nenhum"})

    def test_clahe_pareado_e_parametros_originais_preservados(self):
        for indice, item in enumerate(self.plano["configuracoes"][16:24]):
            referencia = r2.REFERENCIAS[indice // 2]
            self.assertEqual(item["referencia"], referencia)
            self.assertEqual(item["parametros"], self.referencias[referencia]["parametros"])
            self.assertEqual(item["caixa"], self.referencias[referencia]["caixa"])
            self.assertEqual(item["preprocessamento"], {
                "metodo": "clahe", "limite_contraste": (1.0, 2.0)[indice % 2], "grade": [8, 8]})

    def test_metodos_escala_pareiam_caixa_e_limiar_sem_clahe(self):
        for indice, item in enumerate(self.plano["configuracoes"][24:]):
            self.assertEqual(item["metodo"], "log" if indice < 4 else "dog")
            self.assertEqual(item["parametros"]["limiar_resposta"], (0.02, 0.05)[(indice % 4) // 2])
            self.assertEqual(item["parametros"]["polaridade"], "claro")
            self.assertEqual(item["parametros"]["sigma_minimo"], 2)
            self.assertEqual(item["parametros"]["sigma_maximo"], 12)
            self.assertEqual(item["caixa"], ({"modo": "original"}, {"modo": "margem", "pixels": 2})[indice % 2])
            self.assertIsNone(item["referencia"])
            self.assertEqual(item["preprocessamento"], {"metodo": "nenhum"})

    def test_reproducao_sem_sorteios_ou_mutacao_de_entradas(self):
        estado = random.getstate()
        with patch("random.Random", side_effect=AssertionError("Round2 não sorteia.")):
            repetido = r2.gerar_round2(self.origem_bytes)
        self.assertEqual(repetido, self.plano)
        self.assertEqual(random.getstate(), estado)
        self.assertEqual(p.carregar_plano(self.origem_bytes), self.origem)
        for seed in (True, -1, 43):
            with self.subTest(seed=seed), self.assertRaises((ValueError, TypeError)):
                r2.gerar_round2(self.origem_bytes, seed=seed)

    def test_identidade_normaliza_numeros_e_distingue_metodo_contraste_grade(self):
        item = deepcopy(self.plano["configuracoes"][16])
        base = p.hash_configuracao(item)
        item["preprocessamento"]["limite_contraste"] = 1
        self.assertEqual(base, p.hash_configuracao(item))
        item["preprocessamento"]["grade"] = [4, 8]
        self.assertNotEqual(base, p.hash_configuracao(item))
        item = deepcopy(self.plano["configuracoes"][24])
        base = p.hash_configuracao(item)
        item["parametros"]["sigma_minimo"] = 2
        item["caixa"] = {"modo": "escala", "fator": 1}
        self.assertEqual(base, p.hash_configuracao(item))
        self.assertNotEqual(base, p.hash_configuracao(self.plano["configuracoes"][28]))

    def test_nomes_identificam_metodo_preprocessamento_caixa_e_hash(self):
        nomes = []
        for item in self.plano["configuracoes"]:
            nome = p.nome_configuracao(item)
            nomes.append(nome)
            self.assertIn(item["metodo"], nome)
            self.assertIn(item["preprocessamento"]["metodo"], nome)
            self.assertIn(item["caixa"]["modo"], nome)
            self.assertIn(p.hash_configuracao(item)[:12], nome)
            self.assertTrue(nome.isascii())
            self.assertLess(len(nome), 110)
        self.assertEqual(len(set(nomes)), 32)

    def test_rejeita_esquema_referencia_orcamento_e_metodo_invalidos(self):
        for alvo, campo, valor in (("plano", "versao", True), ("plano", "rodada", "round3"),
                                   ("plano", "seed", 43), ("item", "metodo", "desconhecido"),
                                   ("item", "referencia", "r1c49"), ("item", "campo_extra", 0),
                                   ("geracao", "quantidade_controles", True),
                                   ("geracao", "quantidade_exploratorias", 27),
                                   ("geracao", "limite_configuracoes_distintas", 123)):
            with self.subTest(alvo=alvo, campo=campo):
                plano = deepcopy(self.plano)
                objeto = plano if alvo == "plano" else plano["configuracoes"][0] if alvo == "item" else plano["geracao"]
                objeto[campo] = valor
                self.rejeitar(plano)
        plano = deepcopy(self.plano)
        del plano["origem_round1"]
        self.rejeitar(plano)

    def test_rejeita_controle_alterado_refinamento_multiplo_e_pareamento_quebrado(self):
        for indice, secao, campo, valor in ((0, "parametros", "area_minima", 16),
                                           (4, "parametros", "area_minima", 16),
                                           (16, "caixa", "pixels", 5),
                                           (24, "parametros", "limiar_resposta", 0.03)):
            plano = deepcopy(self.plano)
            plano["configuracoes"][indice][secao][campo] = valor
            self.rejeitar(plano)

    def test_rejeita_duplicatas_na_rodada_e_com_round1(self):
        plano = deepcopy(self.plano)
        plano["configuracoes"][5]["caixa"] = deepcopy(plano["configuracoes"][4]["caixa"])
        self.rejeitar(plano)
        plano = deepcopy(self.plano)
        plano["geracao"]["identidades_round1"]["r1c01"] = p.hash_configuracao(plano["configuracoes"][4])
        self.rejeitar(plano)

    def test_vinculo_origem_hash_quadros_fontes_e_identidades(self):
        r2.validar_origem_round1(self.plano, self.origem_bytes)
        for campo in ("hash", "quadro", "fonte", "identidade"):
            plano = deepcopy(self.plano)
            if campo == "hash":
                plano["origem_round1"]["sha256"] = "0" * 64
            elif campo == "quadro":
                plano["quadros"][0]["imagem_sha256"] = "0" * 64
            elif campo == "fonte":
                plano["origem_inspecao"]["sha256"] = "0" * 64
            else:
                plano["geracao"]["identidades_round1"]["r1c01"] = "0" * 64
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                r2.validar_origem_round1(plano, self.origem_bytes)


if __name__ == "__main__":
    unittest.main()
