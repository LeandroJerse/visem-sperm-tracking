"""Contrato v4 e cadeia de planos sintéticos sem execução dos detectores."""

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
from scripts.blobs import planejamento_round4 as r4
from scripts.testes.test_planejamento_blobs import fontes_sinteticas


RAIZ = Path(__file__).resolve().parents[2]
HASHES_CONGELADOS = {
    "round1": "59eba7c3ca133b45c5b581860677add18675a2458fbc65d28d267cf5883b2b69",
    "round2": "29a9ae0de042b1da2a5b5563d9834565e5b8a8069a53e302793389b7435755da",
    "round3": "1b362082bd1fa22b2885a8b3f898c5116c2a34f4915de8c3f7cf374a457bce46",
}


def serializar(dados):
    return json.dumps(dados, ensure_ascii=False, allow_nan=False).encode("utf-8")


class TestPlanejamentoRound4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch("cv2.SimpleBlobDetector_create", side_effect=AssertionError("Detector proibido.")):
            dev, inspecao = fontes_sinteticas()
            p1 = p.gerar_round1(dev, inspecao)
            b1 = serializar(p1)
            p2 = r2.gerar_round2(b1)
            b2 = serializar(p2)
            p3 = r3.gerar_round3(b1, b2)
            b3 = serializar(p3)
            cls.origens = (p1, p2, p3)
            cls.conteudos = (b1, b2, b3)
            cls.referencias = {x["id"]: x for x in p3["configuracoes"]}
            cls.modelo = r4.gerar_round4(b1, b2, b3)

    def setUp(self):
        proibido = patch("cv2.SimpleBlobDetector_create", side_effect=AssertionError("Detector proibido."))
        proibido.start()
        self.addCleanup(proibido.stop)
        self.plano = deepcopy(self.modelo)

    def rejeita(self, plano):
        with self.assertRaises((ValueError, TypeError)):
            p.carregar_plano(serializar(plano))

    def test_18_itens_178_quadros_tres_grades_completas(self):
        plano = p.carregar_plano(serializar(self.plano))
        self.assertEqual(plano, self.plano)
        for origem in self.origens:
            self.assertEqual(plano["quadros"], origem["quadros"])
        self.assertEqual(len(plano["quadros"]), 178)
        itens = plano["configuracoes"]
        self.assertEqual(Counter(x["metodo"] for x in itens), {"simpleblob": 6, "dog": 8, "log": 4})
        self.assertEqual([(x["parametros"]["area_minima"], x["caixa"]["pixels"]) for x in itens[:6]],
                         list(product((48, 64, 80), (2, 3))))
        self.assertEqual([(x["parametros"]["limiar_resposta"], x["caixa"]["pixels"]) for x in itens[6:14]],
                         list(product((0.12, 0.16, 0.20, 0.24), (6, 8))))
        self.assertEqual([(x["parametros"]["limiar_resposta"], x["caixa"]["pixels"]) for x in itens[14:]],
                         list(product((0.08, 0.12), (5, 6))))

    def test_cinco_controles_exatos_nas_celulas_aprovadas(self):
        controles = [x for x in self.plano["configuracoes"] if x["bloco"] == "controle"]
        self.assertEqual({x["id"]: x["referencia"] for x in controles}, {
            "r4c02": "r3c05", "r4c04": "r3c09", "r4c07": "r3c24",
            "r4c16": "r3c16", "r4c18": "r3c18"})
        for item in controles:
            self.assertEqual(p.hash_configuracao(item), p.hash_configuracao(self.referencias[item["referencia"]]))

    def test_simpleblob_fixa_distancia_e_demais_parametros(self):
        base = self.referencias["r3c09"]
        for item in self.plano["configuracoes"][:6]:
            parametros = deepcopy(item["parametros"])
            parametros["area_minima"] = base["parametros"]["area_minima"]
            self.assertEqual(parametros, base["parametros"])
            self.assertEqual(item["parametros"]["distancia_minima"], 6)
            self.assertEqual(item["preprocessamento"], {"metodo": "nenhum"})
            if item["bloco"] == "exploracao":
                self.assertEqual(item["referencia"], "r3c09")

    def test_escalas_preservam_polaridade_sigma_classe_e_preprocessamento(self):
        for item in self.plano["configuracoes"][6:]:
            referencia = "r3c24" if item["metodo"] == "dog" else "r3c18"
            parametros = deepcopy(item["parametros"])
            parametros["limiar_resposta"] = self.referencias[referencia]["parametros"]["limiar_resposta"]
            self.assertEqual(parametros, self.referencias[referencia]["parametros"])
            self.assertEqual(item["preprocessamento"], {"metodo": "nenhum"})
            if item["bloco"] == "exploracao":
                self.assertEqual(item["referencia"], referencia)

    def test_deduplicacao_historica_13_novas_109_distintas_e_saldo(self):
        antigas = {p.hash_configuracao(x) for origem in self.origens for x in origem["configuracoes"]}
        atuais = {p.hash_configuracao(x) for x in self.plano["configuracoes"]}
        self.assertEqual(len(antigas), 96)
        self.assertEqual(len(atuais), 18)
        self.assertEqual(len(antigas & atuais), 5)
        self.assertEqual(len(atuais - antigas), 13)
        self.assertEqual(len(antigas | atuais), 109)
        meta = self.plano["geracao"]
        self.assertEqual(meta["limite_novas_round5"], 13)
        self.assertEqual(meta["quantidade_prevista_round5"], 14)
        self.assertEqual(meta["configuracoes_distintas_acumuladas"] + meta["limite_novas_round5"], 122)

    def test_reproducao_preserva_fontes_e_estado_aleatorio(self):
        estado = random.getstate()
        with patch("random.Random", side_effect=AssertionError("Não sortear parâmetros.")):
            repetido = r4.gerar_round4(*self.conteudos)
        self.assertEqual(repetido, self.plano)
        self.assertEqual(random.getstate(), estado)
        for plano, conteudo in zip(self.origens, self.conteudos):
            self.assertEqual(serializar(plano), conteudo)
        for seed in (True, -1, 43):
            with self.subTest(seed=seed), self.assertRaises((ValueError, TypeError)):
                r4.gerar_round4(*self.conteudos, seed=seed)

    def test_hashes_planos_congelados_v1_v2_v3_preservados(self):
        for rodada, digest in HASHES_CONGELADOS.items():
            conteudo = (RAIZ / f"scripts/blobs/rodadas/{rodada}.json").read_bytes()
            self.assertEqual(hashlib.sha256(conteudo).hexdigest(), digest)
            plano = p.carregar_plano(conteudo)
            self.assertEqual(plano["rodada"], rodada)
            self.assertEqual(len({p.nome_configuracao(x) for x in plano["configuracoes"]}), len(plano["configuracoes"]))

    def test_schema_topo_itens_e_metadata_estritos(self):
        casos = (("plano", "versao", True), ("plano", "rodada", "round5"),
                 ("plano", "seed", 43), ("item", "extra", 1), ("item", "referencia", "r2c01"),
                 ("item", "referencia", "r3c25"), ("geracao", "quantidade_controles", 4),
                 ("geracao", "quantidade_exploratorias", 14),
                 ("geracao", "configuracoes_distintas_acumuladas", 110),
                 ("geracao", "limite_novas_round5", 14))
        for alvo, campo, valor in casos:
            with self.subTest(alvo=alvo, campo=campo):
                plano = deepcopy(self.plano)
                dado = plano if alvo == "plano" else plano["configuracoes"][0] if alvo == "item" else plano["geracao"]
                dado[campo] = valor
                self.rejeita(plano)
        for campo in ("origem_round1", "origem_round2", "origem_round3"):
            plano = deepcopy(self.plano)
            del plano[campo]
            self.rejeita(plano)

    def test_rejeita_ausencias_duplicatas_reordenacao_e_controles_falsos(self):
        for tipo in ("ausencia", "duplicata", "ordem", "controle"):
            plano = deepcopy(self.plano)
            if tipo == "ausencia":
                plano["configuracoes"].pop()
            elif tipo == "duplicata":
                plano["configuracoes"][0]["caixa"]["pixels"] = 3
            elif tipo == "ordem":
                plano["configuracoes"][0], plano["configuracoes"][1] = plano["configuracoes"][1], plano["configuracoes"][0]
                for i, item in enumerate(plano["configuracoes"], 1):
                    item["id"] = f"r4c{i:02d}"
            else:
                plano["configuracoes"][0]["bloco"] = "controle"
            with self.subTest(tipo=tipo):
                self.rejeita(plano)

    def test_rejeita_drift_de_fatores_parametros_fixos_e_classificacao(self):
        for indice, campo, valor in ((0, "distancia_minima", 12), (4, "area_minima", 96),
                                     (6, "sigma_minimo", 3), (8, "razao_sigma", 1.5),
                                     (14, "numero_escalas", 12), (16, "limiar_resposta", 0.2)):
            plano = deepcopy(self.plano)
            plano["configuracoes"][indice]["parametros"][campo] = valor
            self.rejeita(plano)
        plano = deepcopy(self.plano)
        plano["configuracoes"][0]["parametros"]["classificacao"]["area_maxima_pequeno"] = 40
        self.rejeita(plano)
        plano = deepcopy(self.plano)
        plano["configuracoes"][0]["preprocessamento"] = {"metodo": "clahe", "limite_contraste": 1, "grade": [8, 8]}
        self.rejeita(plano)
        plano = deepcopy(self.plano)
        plano["configuracoes"][14]["caixa"]["pixels"] = 8
        self.rejeita(plano)

    def test_cadeia_completa_confere_hashes_quadros_e_fontes(self):
        r4.validar_origens_round4(self.plano, *self.conteudos)
        for campo in ("origem_round1", "origem_round2", "origem_round3", "origem_inspecao", "origem_desenvolvimento", "quadro"):
            plano = deepcopy(self.plano)
            if campo == "quadro":
                plano["quadros"][0]["anotacao_sha256"] = "0" * 64
            else:
                plano[campo]["sha256"] = "0" * 64
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                r4.validar_origens_round4(plano, *self.conteudos)
        origem = deepcopy(self.origens[2])
        origem["quadros"][0]["imagem_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            r4.gerar_round4(self.conteudos[0], self.conteudos[1], serializar(origem))

    def test_identidades_historicas_falsas_ou_repeticoes_ocultas_rejeitadas(self):
        for campo, id in (("identidades_round1", "r1c01"),
                          ("identidades_round2", "r2c09"), ("identidades_round3", "r3c01")):
            plano = deepcopy(self.plano)
            plano["geracao"][campo][id] = "0" * 64
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                r4.validar_origens_round4(plano, *self.conteudos)
        plano = deepcopy(self.plano)
        plano["geracao"]["identidades_round1"]["r1c01"] = p.hash_configuracao(plano["configuracoes"][0])
        self.rejeita(plano)

    def test_rejeita_fontes_ou_plano_de_rodada_errada(self):
        with self.assertRaises(ValueError):
            r4.gerar_round4(self.conteudos[0], self.conteudos[2], self.conteudos[1])
        with self.assertRaises(ValueError):
            r4.validar_origens_round4(self.origens[2], *self.conteudos)

    def test_nomes_identidade_e_numeros_equivalentes(self):
        nomes = [p.nome_configuracao(item) for item in self.plano["configuracoes"]]
        self.assertEqual(len(set(nomes)), 18)
        for item, nome in zip(self.plano["configuracoes"], nomes):
            self.assertLess(len(nome), 80)
            self.assertIn(item["metodo"], nome)
            self.assertIn("nenhum", nome)
            self.assertIn(p.hash_configuracao(item)[:12], nome)
            equivalente = deepcopy(item)
            equivalente.update(id="r4c99", bloco="exploracao", referencia=None, perfil_forma="metadado")
            equivalente["caixa"]["pixels"] = float(equivalente["caixa"]["pixels"])
            self.assertEqual(p.hash_configuracao(equivalente), p.hash_configuracao(item))


if __name__ == "__main__":
    unittest.main()
