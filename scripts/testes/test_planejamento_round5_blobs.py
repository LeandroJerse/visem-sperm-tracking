"""Contrato final de desenvolvimento e contraste LoG com fontes sintéticas."""

from collections import Counter
from copy import deepcopy
import hashlib
from itertools import product
import json
from math import pi
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from algoritmos.classicos.variantes_blobs import configuracao_escala_de_dict, parametros_escala
from scripts.blobs import planejamento as p
from scripts.blobs import planejamento_round2 as r2
from scripts.blobs import planejamento_round3 as r3
from scripts.blobs import planejamento_round4 as r4
from scripts.blobs import planejamento_round5 as r5
from scripts.testes.test_planejamento_blobs import fontes_sinteticas


RAIZ = Path(__file__).resolve().parents[2]
HASHES_CONGELADOS = {
    "round1": "59eba7c3ca133b45c5b581860677add18675a2458fbc65d28d267cf5883b2b69",
    "round2": "29a9ae0de042b1da2a5b5563d9834565e5b8a8069a53e302793389b7435755da",
    "round3": "1b362082bd1fa22b2885a8b3f898c5116c2a34f4915de8c3f7cf374a457bce46",
    "round4": "f5d69b234435e2dfa64e681dc44eaac651fcf7a4eb9667a21e03a46ad62e154e",
}


def serializar(dados):
    return json.dumps(dados, ensure_ascii=False, allow_nan=False).encode("utf-8")


class TestPlanejamentoRound5(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch("cv2.SimpleBlobDetector_create", side_effect=AssertionError("Detector proibido.")):
            dev, inspecao = fontes_sinteticas()
            plano1 = p.gerar_round1(dev, inspecao)
            b1 = serializar(plano1)
            plano2 = r2.gerar_round2(b1)
            b2 = serializar(plano2)
            plano3 = r3.gerar_round3(b1, b2)
            b3 = serializar(plano3)
            plano4 = r4.gerar_round4(b1, b2, b3)
            b4 = serializar(plano4)
            cls.origens = (plano1, plano2, plano3, plano4)
            cls.conteudos = (b1, b2, b3, b4)
            cls.referencias = {x["id"]: x for x in plano4["configuracoes"]}
            cls.modelo = r5.gerar_round5(b1, b2, b3, b4)

    def setUp(self):
        proibido = patch("cv2.SimpleBlobDetector_create", side_effect=AssertionError("Detector proibido."))
        proibido.start()
        self.addCleanup(proibido.stop)
        self.plano = deepcopy(self.modelo)

    def rejeita(self, plano):
        with self.assertRaises((ValueError, TypeError)):
            p.carregar_plano(serializar(plano))

    def test_14_itens_178_quadros_e_grades_locais_completas(self):
        plano = p.carregar_plano(serializar(self.plano))
        self.assertEqual(plano, self.plano)
        for origem in self.origens:
            self.assertEqual(plano["quadros"], origem["quadros"])
        self.assertEqual(len(plano["quadros"]), 178)
        itens = plano["configuracoes"]
        self.assertEqual(Counter(x["metodo"] for x in itens), {"simpleblob": 6, "dog": 6, "log": 2})
        self.assertEqual([(x["parametros"]["area_minima"], x["caixa"]["pixels"]) for x in itens[:6]],
                         list(product((56, 64, 72), (2, 3))))
        self.assertEqual([(x["parametros"]["limiar_resposta"], x["caixa"]["pixels"]) for x in itens[6:12]],
                         list(product((0.10, 0.12, 0.14), (5, 6))))

    def test_quatro_controles_exatos_nas_posicoes_aprovadas(self):
        controles = [x for x in self.plano["configuracoes"] if x["bloco"] == "controle"]
        self.assertEqual({x["id"]: x["referencia"] for x in controles}, {
            "r5c03": "r4c03", "r5c04": "r4c04", "r5c10": "r4c07", "r5c13": "r4c18"})
        for item in controles:
            self.assertEqual(p.hash_configuracao(item), p.hash_configuracao(self.referencias[item["referencia"]]))

    def test_simpleblob_fixa_distancia_demais_parametros_e_classificacao(self):
        base = self.referencias["r4c04"]
        for item in self.plano["configuracoes"][:6]:
            parametros = deepcopy(item["parametros"])
            parametros["area_minima"] = base["parametros"]["area_minima"]
            self.assertEqual(parametros, base["parametros"])
            self.assertEqual(item["parametros"]["distancia_minima"], 6)
            self.assertEqual(item["preprocessamento"], {"metodo": "nenhum"})
            if item["bloco"] == "exploracao":
                self.assertEqual(item["referencia"], "r4c04")

    def test_dog_varia_somente_resposta_e_margem(self):
        base = self.referencias["r4c07"]
        for item in self.plano["configuracoes"][6:12]:
            parametros = deepcopy(item["parametros"])
            parametros["limiar_resposta"] = base["parametros"]["limiar_resposta"]
            self.assertEqual(parametros, base["parametros"])
            self.assertEqual(item["referencia"], "r4c07")
            self.assertEqual(item["preprocessamento"], {"metodo": "nenhum"})

    def test_log_altera_exatamente_um_limite_sem_mudar_detector(self):
        controle, variante = self.plano["configuracoes"][12:]
        self.assertEqual(controle["referencia"], "r4c18")
        self.assertEqual(variante["referencia"], "r4c18")
        self.assertEqual(controle["parametros"], self.referencias["r4c18"]["parametros"])
        self.assertEqual(controle["parametros"]["classificacao"]["area_minima_aglomerado"], pi * 12 ** 2)
        self.assertEqual(variante["parametros"]["classificacao"]["area_minima_aglomerado"], pi * 14 ** 2)
        restaurado = deepcopy(variante["parametros"])
        restaurado["classificacao"]["area_minima_aglomerado"] = pi * 12 ** 2
        self.assertEqual(restaurado, controle["parametros"])
        self.assertEqual(variante["caixa"], controle["caixa"])
        self.assertEqual(variante["preprocessamento"], controle["preprocessamento"])
        self.assertEqual(parametros_escala(configuracao_escala_de_dict("log", controle["parametros"])),
                         parametros_escala(configuracao_escala_de_dict("log", variante["parametros"])))
        self.assertNotEqual(p.hash_configuracao(controle), p.hash_configuracao(variante))

    def test_deduplicacao_10_novas_119_distintas_136_posicoes(self):
        antigas = {p.hash_configuracao(x) for origem in self.origens for x in origem["configuracoes"]}
        atuais = {p.hash_configuracao(x) for x in self.plano["configuracoes"]}
        self.assertEqual(len(antigas), 109)
        self.assertEqual(len(atuais), 14)
        self.assertEqual(len(antigas & atuais), 4)
        self.assertEqual(len(atuais - antigas), 10)
        self.assertEqual(len(antigas | atuais), 119)
        self.assertEqual(sum(len(x["configuracoes"]) for x in self.origens) + len(atuais), 136)
        self.assertEqual(self.plano["geracao"]["limite_configuracoes_distintas"], 122)
        self.assertEqual(self.plano["geracao"]["total_configuracoes_nas_cinco_rodadas"], 136)

    def test_reproducao_sem_sorteio_ou_mutacao(self):
        estado = random.getstate()
        with patch("random.Random", side_effect=AssertionError("Não sortear parâmetros.")):
            repetido = r5.gerar_round5(*self.conteudos)
        self.assertEqual(repetido, self.plano)
        self.assertEqual(random.getstate(), estado)
        for plano, conteudo in zip(self.origens, self.conteudos):
            self.assertEqual(serializar(plano), conteudo)
        for seed in (True, -1, 43):
            with self.subTest(seed=seed), self.assertRaises((ValueError, TypeError)):
                r5.gerar_round5(*self.conteudos, seed=seed)

    def test_hashes_dos_quatro_planos_congelados_preservados(self):
        for rodada, digest in HASHES_CONGELADOS.items():
            conteudo = (RAIZ / f"scripts/blobs/rodadas/{rodada}.json").read_bytes()
            self.assertEqual(hashlib.sha256(conteudo).hexdigest(), digest)
            plano = p.carregar_plano(conteudo)
            self.assertEqual(plano["rodada"], rodada)
            self.assertEqual(len({p.nome_configuracao(x) for x in plano["configuracoes"]}), len(plano["configuracoes"]))

    def test_esquema_fontes_referencias_e_orcamento_estritos(self):
        casos = (("plano", "versao", True), ("plano", "rodada", "round4"), ("plano", "seed", 43),
                 ("item", "extra", 1), ("item", "referencia", "r3c09"), ("item", "referencia", "r4c19"),
                 ("geracao", "quantidade_controles", 5), ("geracao", "quantidade_exploratorias", 9),
                 ("geracao", "configuracoes_distintas_acumuladas", 122),
                 ("geracao", "total_configuracoes_nas_cinco_rodadas", 137))
        for alvo, campo, valor in casos:
            with self.subTest(alvo=alvo, campo=campo):
                plano = deepcopy(self.plano)
                dado = plano if alvo == "plano" else plano["configuracoes"][0] if alvo == "item" else plano["geracao"]
                dado[campo] = valor
                self.rejeita(plano)
        for i in (1, 2, 3, 4):
            plano = deepcopy(self.plano)
            del plano[f"origem_round{i}"]
            self.rejeita(plano)
        plano = deepcopy(self.plano)
        plano["origem_round4"]["plano"] = "../round4.json"
        self.rejeita(plano)

    def test_rejeita_celulas_ausentes_duplicadas_ou_reordenadas(self):
        for tipo in ("ausencia", "duplicata", "ordem"):
            plano = deepcopy(self.plano)
            if tipo == "ausencia":
                plano["configuracoes"].pop()
            elif tipo == "duplicata":
                plano["configuracoes"][0]["caixa"]["pixels"] = 3
            else:
                plano["configuracoes"][0], plano["configuracoes"][1] = plano["configuracoes"][1], plano["configuracoes"][0]
                for i, item in enumerate(plano["configuracoes"], 1):
                    item["id"] = f"r5c{i:02d}"
            with self.subTest(tipo=tipo):
                self.rejeita(plano)

    def test_rejeita_drift_de_parametros_fixos_e_limite_log_nao_aprovado(self):
        for indice, campo, valor in ((0, "distancia_minima", 12), (4, "area_minima", 80),
                                     (6, "sigma_minimo", 3), (8, "razao_sigma", 1.5),
                                     (12, "numero_escalas", 12), (13, "limiar_resposta", 0.08)):
            plano = deepcopy(self.plano)
            plano["configuracoes"][indice]["parametros"][campo] = valor
            self.rejeita(plano)
        for campo, valor in (("area_minima_aglomerado", pi * 16 ** 2), ("area_maxima_pequeno", 100)):
            plano = deepcopy(self.plano)
            plano["configuracoes"][13]["parametros"]["classificacao"][campo] = valor
            self.rejeita(plano)
        plano = deepcopy(self.plano)
        plano["configuracoes"][13]["caixa"]["pixels"] = 5
        self.rejeita(plano)

    def test_cadeia_completa_rejeita_hashes_quadros_ou_fontes_divergentes(self):
        r5.validar_origens_round5(self.plano, *self.conteudos)
        for campo in ("origem_round1", "origem_round2", "origem_round3", "origem_round4",
                      "origem_inspecao", "origem_desenvolvimento", "quadro"):
            plano = deepcopy(self.plano)
            if campo == "quadro":
                plano["quadros"][0]["anotacao_sha256"] = "0" * 64
            else:
                plano[campo]["sha256"] = "0" * 64
            with self.subTest(campo=campo), self.assertRaises(ValueError):
                r5.validar_origens_round5(plano, *self.conteudos)
        origem = deepcopy(self.origens[3])
        origem["quadros"][0]["imagem_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            r5.gerar_round5(*self.conteudos[:3], serializar(origem))

    def test_identidades_falsas_controles_falsos_e_repeticoes_ocultas_rejeitados(self):
        for i, id in ((1, "r1c01"), (2, "r2c09"), (3, "r3c01"), (4, "r4c05")):
            plano = deepcopy(self.plano)
            plano["geracao"][f"identidades_round{i}"][id] = "0" * 64
            with self.subTest(i=i), self.assertRaises(ValueError):
                r5.validar_origens_round5(plano, *self.conteudos)
        plano = deepcopy(self.plano)
        plano["geracao"]["identidades_round1"]["r1c01"] = p.hash_configuracao(plano["configuracoes"][0])
        self.rejeita(plano)
        plano = deepcopy(self.plano)
        plano["configuracoes"][13]["bloco"] = "controle"
        self.rejeita(plano)

    def test_gerador_e_validador_rejeitam_rodadas_erradas(self):
        with self.assertRaises(ValueError):
            r5.gerar_round5(self.conteudos[0], self.conteudos[1], self.conteudos[3], self.conteudos[2])
        with self.assertRaises(ValueError):
            r5.validar_origens_round5(self.origens[3], *self.conteudos)

    def test_nomes_e_hashes_preservam_semantica(self):
        nomes = [p.nome_configuracao(item) for item in self.plano["configuracoes"]]
        self.assertEqual(len(set(nomes)), 14)
        for item, nome in zip(self.plano["configuracoes"], nomes):
            self.assertLess(len(nome), 80)
            self.assertIn(item["metodo"], nome)
            self.assertIn(p.hash_configuracao(item)[:12], nome)
            equivalente = deepcopy(item)
            equivalente.update(id="r5c99", bloco="exploracao", referencia=None, perfil_forma="metadado")
            equivalente["caixa"]["pixels"] = float(equivalente["caixa"]["pixels"])
            self.assertEqual(p.hash_configuracao(equivalente), p.hash_configuracao(item))


if __name__ == "__main__":
    unittest.main()
