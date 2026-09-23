"""Grades do round3 e cadeia de fontes sintéticas, sem ler imagens ou detectar."""

from collections import Counter
from copy import deepcopy
import hashlib
from itertools import product
import json
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from scripts.blobs import planejamento as p
from scripts.blobs import planejamento_round2 as r2
from scripts.blobs import planejamento_round3 as r3
from scripts.testes.test_planejamento_blobs import fontes_sinteticas


RAIZ = Path(__file__).resolve().parents[2]
HASHES_CONGELADOS = {
    "round1": "59eba7c3ca133b45c5b581860677add18675a2458fbc65d28d267cf5883b2b69",
    "round2": "29a9ae0de042b1da2a5b5563d9834565e5b8a8069a53e302793389b7435755da",
}


def serializar(dados):
    return json.dumps(dados, ensure_ascii=False, allow_nan=False).encode("utf-8")


class TestPlanejamentoRound3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dev, inspecao = fontes_sinteticas()
        cls.round1 = p.gerar_round1(dev, inspecao)
        cls.bytes1 = serializar(cls.round1)
        cls.round2 = r2.gerar_round2(cls.bytes1)
        cls.bytes2 = serializar(cls.round2)
        cls.referencias = {x["id"]: x for x in cls.round2["configuracoes"]}

    def setUp(self):
        detector = patch("cv2.SimpleBlobDetector_create", side_effect=AssertionError("Detector proibido."))
        detector.start()
        self.addCleanup(detector.stop)
        self.plano = r3.gerar_round3(self.bytes1, self.bytes2)

    def rejeita(self, plano):
        with self.assertRaises((ValueError, TypeError)):
            p.carregar_plano(serializar(plano))

    def test_24_configuracoes_178_quadros_e_duas_grades_completas(self):
        plano = p.carregar_plano(serializar(self.plano))
        self.assertEqual(plano, self.plano)
        self.assertEqual(plano["quadros"], self.round1["quadros"])
        self.assertEqual(plano["quadros"], self.round2["quadros"])
        self.assertEqual(len(plano["quadros"]), 178)
        itens = plano["configuracoes"]
        self.assertEqual(len(itens), 24)
        self.assertEqual(Counter(x["metodo"] for x in itens), {"simpleblob": 12, "log": 6, "dog": 6})
        self.assertEqual([(x["parametros"]["area_minima"], x["parametros"]["distancia_minima"],
                           x["caixa"]["pixels"]) for x in itens[:12]],
                         list(product((32, 48, 64), (6, 12), (3, 4))))
        self.assertEqual([(x["metodo"], x["parametros"]["limiar_resposta"], x["caixa"]["pixels"])
                          for x in itens[12:]], list(product(("log", "dog"), (0.05, 0.08, 0.12), (4, 6))))

    def test_quatro_controles_nas_celulas_corretas_nao_no_inicio(self):
        controles = [x for x in self.plano["configuracoes"] if x["bloco"] == "controle"]
        self.assertEqual({x["id"]: x["referencia"] for x in controles}, r3.IDS_CONTROLES)
        self.assertEqual([x["id"] for x in controles], ["r3c02", "r3c03", "r3c04", "r3c08"])
        self.assertEqual(self.plano["configuracoes"][0]["bloco"], "exploracao")
        for item in controles:
            self.assertEqual(p.hash_configuracao(item), p.hash_configuracao(self.referencias[item["referencia"]]))

    def test_somente_tres_fatores_simpleblob_variam(self):
        base = self.referencias["r2c01"]
        for item in self.plano["configuracoes"][:12]:
            parametros = deepcopy(item["parametros"])
            for campo in ("area_minima", "distancia_minima"):
                parametros[campo] = base["parametros"][campo]
            self.assertEqual(parametros, base["parametros"])
            self.assertEqual(item["preprocessamento"], {"metodo": "nenhum"})
            self.assertEqual(item["perfil_forma"], base["perfil_forma"])
            if item["bloco"] == "exploracao":
                self.assertEqual(item["referencia"], "r2c01")

    def test_escalas_mantem_origens_e_so_resposta_e_margem_variam(self):
        for item in self.plano["configuracoes"][12:]:
            referencia = "r2c28" if item["metodo"] == "log" else "r2c32"
            self.assertEqual(item["referencia"], referencia)
            self.assertEqual(item["bloco"], "exploracao")
            parametros = deepcopy(item["parametros"])
            parametros["limiar_resposta"] = 0.05
            self.assertEqual(parametros, self.referencias[referencia]["parametros"])
            self.assertEqual(item["preprocessamento"], {"metodo": "nenhum"})
            historico = deepcopy(item)
            historico["parametros"] = parametros
            historico["caixa"] = {"modo": "margem", "pixels": 2}
            self.assertEqual(p.hash_configuracao(historico), p.hash_configuracao(self.referencias[referencia]))

    def test_sem_duplicatas_20_novas_96_acumuladas(self):
        antigas = {p.hash_configuracao(x) for x in self.round1["configuracoes"] + self.round2["configuracoes"]}
        novas = {p.hash_configuracao(x) for x in self.plano["configuracoes"]}
        self.assertEqual(len(antigas), 76)
        self.assertEqual(len(novas), 24)
        self.assertEqual(len(antigas & novas), 4)
        self.assertEqual(len(novas - antigas), 20)
        self.assertEqual(len(antigas | novas), 96)

    def test_reproducao_sem_sorteio_mutacao_ou_seed_alternativa(self):
        estado = random.getstate()
        with patch("random.Random", side_effect=AssertionError("Não sortear.")):
            repetido = r3.gerar_round3(self.bytes1, self.bytes2)
        self.assertEqual(repetido, self.plano)
        self.assertEqual(random.getstate(), estado)
        self.assertEqual(serializar(self.round1), self.bytes1)
        self.assertEqual(serializar(self.round2), self.bytes2)
        for seed in (True, -1, 43):
            with self.subTest(seed=seed), self.assertRaises((ValueError, TypeError)):
                r3.gerar_round3(self.bytes1, self.bytes2, seed=seed)

    def test_planos_anteriores_e_identidades_permanecem_inalterados(self):
        for rodada, digest in HASHES_CONGELADOS.items():
            conteudo = (RAIZ / f"scripts/blobs/rodadas/{rodada}.json").read_bytes()
            self.assertEqual(hashlib.sha256(conteudo).hexdigest(), digest)
            plano = p.carregar_plano(conteudo)
            self.assertEqual(plano["rodada"], rodada)
        for item in self.round1["configuracoes"]:
            equivalente = deepcopy(item)
            equivalente.update(metodo="simpleblob", preprocessamento={"metodo": "nenhum"})
            self.assertEqual(p.hash_configuracao(item), p.hash_configuracao(equivalente))

    def test_esquema_orcamentos_e_fontes_exigem_chaves_exatas(self):
        for alvo, campo, valor in (("plano", "versao", True), ("plano", "rodada", "round4"),
                                   ("plano", "seed", 43), ("item", "campo_extra", 1),
                                   ("item", "referencia", "r1c29"), ("item", "referencia", "r2c33"),
                                   ("geracao", "quantidade_controles", 5),
                                   ("geracao", "quantidade_exploratorias", 19),
                                   ("geracao", "configuracoes_distintas_acumuladas", 95),
                                   ("geracao", "limite_configuracoes_distintas", 123)):
            with self.subTest(alvo=alvo, campo=campo):
                plano = deepcopy(self.plano)
                dado = plano if alvo == "plano" else plano["configuracoes"][0] if alvo == "item" else plano["geracao"]
                dado[campo] = valor
                self.rejeita(plano)
        for campo in ("origem_round1", "origem_round2"):
            plano = deepcopy(self.plano)
            del plano[campo]
            self.rejeita(plano)
        plano = deepcopy(self.plano)
        plano["origem_round2"]["plano"] = "../round2.json"
        self.rejeita(plano)

    def test_rejeita_celulas_ausentes_duplicadas_reordenadas_ou_renomeadas(self):
        plano = deepcopy(self.plano)
        plano["configuracoes"].pop()
        self.rejeita(plano)
        plano = deepcopy(self.plano)
        plano["configuracoes"][0]["caixa"]["pixels"] = 4
        self.rejeita(plano)
        plano = deepcopy(self.plano)
        plano["configuracoes"][0], plano["configuracoes"][1] = plano["configuracoes"][1], plano["configuracoes"][0]
        for i, item in enumerate(plano["configuracoes"], 1):
            item["id"] = f"r3c{i:02d}"
        self.rejeita(plano)

    def test_rejeita_drift_de_parametros_fixos_e_classificacao(self):
        for indice, secao, campo, valor in ((0, "parametros", "area_maxima", 600),
                                           (1, "parametros", "distancia_minima", 7),
                                           (12, "parametros", "sigma_minimo", 3),
                                           (18, "parametros", "razao_sigma", 1.5),
                                           (23, "parametros", "limiar_resposta", 0.13)):
            plano = deepcopy(self.plano)
            plano["configuracoes"][indice][secao][campo] = valor
            self.rejeita(plano)
        plano = deepcopy(self.plano)
        plano["configuracoes"][12]["parametros"]["classificacao"]["area_maxima_pequeno"] = 100
        self.rejeita(plano)
        plano = deepcopy(self.plano)
        plano["configuracoes"][0]["preprocessamento"] = {"metodo": "clahe", "limite_contraste": 1, "grade": [8, 8]}
        self.rejeita(plano)

    def test_rejeita_controle_falso_e_repeticao_historica_oculta(self):
        plano = deepcopy(self.plano)
        plano["configuracoes"][0]["bloco"] = "controle"
        self.rejeita(plano)
        plano = deepcopy(self.plano)
        plano["configuracoes"][12]["bloco"] = "controle"
        self.rejeita(plano)
        plano = deepcopy(self.plano)
        plano["geracao"]["identidades_round1"]["r1c01"] = p.hash_configuracao(plano["configuracoes"][0])
        self.rejeita(plano)

    def test_cadeia_de_fontes_vincula_hashes_quadros_e_identidades(self):
        r3.validar_origens_round3(self.plano, self.bytes1, self.bytes2)
        for campo in ("origem_round1", "origem_round2", "origem_inspecao", "origem_desenvolvimento", "quadro", "identidade"):
            plano = deepcopy(self.plano)
            if campo == "quadro":
                plano["quadros"][0]["imagem_sha256"] = "0" * 64
            elif campo == "identidade":
                plano["geracao"]["identidades_round1"]["r1c01"] = "0" * 64
            else:
                plano[campo]["sha256"] = "0" * 64
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                r3.validar_origens_round3(plano, self.bytes1, self.bytes2)
        alterada = deepcopy(self.round2)
        alterada["quadros"][0]["imagem_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            r3.gerar_round3(self.bytes1, serializar(alterada))

    def test_geracao_e_validador_rejeitam_rodadas_erradas(self):
        with self.assertRaises(ValueError):
            r3.gerar_round3(self.bytes2, self.bytes1)
        with self.assertRaises(ValueError):
            r3.validar_origens_round3(self.round2, self.bytes1, self.bytes2)

    def test_nomes_unicos_e_hashes_sem_dependencia_da_identificacao(self):
        nomes = [p.nome_configuracao(x) for x in self.plano["configuracoes"]]
        self.assertEqual(len(set(nomes)), 24)
        for item, nome in zip(self.plano["configuracoes"], nomes):
            self.assertIn(item["metodo"], nome)
            self.assertIn("nenhum", nome)
            self.assertIn(p.hash_configuracao(item)[:12], nome)
            self.assertLess(len(nome), 80)
            alterado = deepcopy(item)
            alterado.update(id="r3c99", referencia=None, perfil_forma="somente_metadado", bloco="exploracao")
            self.assertEqual(p.hash_configuracao(item), p.hash_configuracao(alterado))


if __name__ == "__main__":
    unittest.main()
