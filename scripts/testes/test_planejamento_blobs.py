"""Planos sintéticos: composição, reprodução e rejeição de desvios do desenho."""

from collections import Counter
from copy import deepcopy
import hashlib
import json
from math import pi
import random
import unittest
from unittest.mock import patch

from scripts.blobs import planejamento as p


def serializar(dados):
    return json.dumps(dados, ensure_ascii=False, allow_nan=False).encode("utf-8")


def fontes_sinteticas():
    quadros = []
    for video in ("11", "12", "15", "19", "21", "22", "23", "30", "35", "36", "47", "60"):
        for quadro in range(0, 1401, 100):
            if video == "23" and quadro in (900, 1100):
                continue
            nome = f"{video}_frame_{quadro}"
            base = f"bases_de_dados/visem_tracking/dataset/Train/{video}"
            quadros.append({
                "video_id": video, "quadro": quadro,
                "imagem": f"{base}/images/{nome}.jpg", "anotacao": f"{base}/labels/{nome}.txt",
                "sha256_imagem": hashlib.sha256(f"imagem:{nome}".encode()).hexdigest(),
                "sha256_anotacao": hashlib.sha256(f"anotacao:{nome}".encode()).hexdigest(),
            })
    desenvolvimento = {"versao": 1, "algoritmo": "limiarizacao", "rodada": "round1",
                       "particao": "desenvolvimento", "quadros": quadros}
    dev_bytes = serializar(desenvolvimento)
    referencias = []
    for indice, polaridade in enumerate(("claro", "escuro"), 1):
        referencias.append({"id": f"b{indice:02d}", "parametros": {
            "polaridade": polaridade, "limiar_minimo": 10, "limiar_maximo": 250,
            "passo_limiar": 10, "repetibilidade_minima": 2, "distancia_minima": 3,
            "area_minima": 3, "area_maxima": 5000, "circularidade_minima": None,
            "inercia_minima": None, "convexidade_minima": None,
            "classificacao": {"area_maxima_pequeno": pi * 16, "area_minima_aglomerado": pi * 144},
        }})
    escolhidos = {("11", 0), ("12", 200), ("19", 0), ("21", 0), ("23", 0), ("36", 1300)}
    inspecao = {
        "versao": 1, "algoritmo": "blobs", "etapa": "inspecao", "rodada": "round0",
        "particao": "desenvolvimento", "seed": 42,
        "origem_desenvolvimento": {"plano": p.ORIGEM_DESENVOLVIMENTO,
                                   "sha256": hashlib.sha256(dev_bytes).hexdigest()},
        "quadros": [{k: q[k] for k in ("video_id", "quadro", "imagem", "anotacao")} | {
            "imagem_sha256": q["sha256_imagem"], "anotacao_sha256": q["sha256_anotacao"],
            "objetivo": "Caso sintético, sem imagem ou detector.",
        } for q in quadros if (q["video_id"], q["quadro"]) in escolhidos],
        "configuracoes": referencias, "observacoes": [],
    }
    return dev_bytes, serializar(inspecao)


class TestPlanejamentoBlobs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dev, cls.inspecao = fontes_sinteticas()

    def setUp(self):
        # A geração de planos nunca deve construir ou executar o detector.
        self.backend = patch("cv2.SimpleBlobDetector_create", side_effect=AssertionError("Detector proibido neste teste."))
        self.backend.start()
        self.addCleanup(self.backend.stop)
        self.plano = p.gerar_round1(self.dev, self.inspecao)

    def rejeita(self, plano):
        with self.assertRaises((ValueError, TypeError)):
            p.carregar_plano(serializar(plano))

    def test_48_configuracoes_178_quadros_e_balanceamento_independente(self):
        self.assertEqual(p.carregar_plano(serializar(self.plano)), self.plano)
        configs = self.plano["configuracoes"]
        self.assertEqual(len(configs), 48)
        self.assertEqual(len({p.hash_configuracao(x) for x in configs}), 48)
        self.assertEqual(len(self.plano["quadros"]), 178)
        self.assertEqual(Counter(x["parametros"]["polaridade"] for x in configs), {"claro": 24, "escuro": 24})
        self.assertEqual(Counter(x["caixa"]["modo"] for x in configs), {"original": 14, "escala": 18, "margem": 16})
        self.assertEqual(Counter(x["bloco"] for x in configs), {"controle": 12, "exploracao": 36})
        for polaridade in ("claro", "escuro"):
            for modo in ("original", "escala", "margem"):
                grupo = [x for x in configs[12:] if x["parametros"]["polaridade"] == polaridade and x["caixa"]["modo"] == modo]
                self.assertEqual(len(grupo), 6)
                self.assertEqual(len({x["perfil_forma"] for x in grupo}), 6)
                for campo, valores in (("limiar_minimo", [10, 40, 80]),
                                      ("area_minima", [3, 8, 16, 32])):
                    contagens = Counter(x["parametros"][campo] for x in grupo)
                    self.assertEqual(set(contagens), set(valores))
                    self.assertLessEqual(max(contagens.values()) - min(contagens.values()), 1)
                for item in grupo:
                    filtros = [item["parametros"][k] for k in ("circularidade_minima", "inercia_minima", "convexidade_minima")]
                    self.assertLessEqual(sum(v is not None for v in filtros), 1)

    def test_reproducao_controles_e_estado_aleatorio_global_preservados(self):
        estado = random.getstate()
        repetido = p.gerar_round1(self.dev, self.inspecao, seed=42)
        outro = p.gerar_round1(self.dev, self.inspecao, seed=43)
        self.assertEqual(repetido, self.plano)
        self.assertEqual(estado, random.getstate())
        self.assertEqual(outro["configuracoes"][:12], repetido["configuracoes"][:12])
        self.assertNotEqual(outro["configuracoes"][12:], repetido["configuracoes"][12:])
        referencias = json.loads(self.inspecao)["configuracoes"]
        for i, item in enumerate(repetido["configuracoes"][:12]):
            self.assertEqual(item["parametros"], referencias[i // 6]["parametros"])
        self.assertEqual((self.dev, self.inspecao), fontes_sinteticas())

    def test_identidade_efetiva_float32_numeros_e_caixas_equivalentes(self):
        original = self.plano["configuracoes"][0]
        equivalente = deepcopy(original)
        equivalente["parametros"]["distancia_minima"] = 3.000000001
        equivalente["caixa"] = {"modo": "escala", "fator": 1.0}
        self.assertEqual(p.hash_configuracao(original), p.hash_configuracao(equivalente))
        equivalente["caixa"] = {"modo": "margem", "pixels": 0}
        self.assertEqual(p.hash_configuracao(original), p.hash_configuracao(equivalente))
        equivalente["parametros"]["classificacao"]["area_maxima_pequeno"] += 1e-9
        self.assertNotEqual(p.hash_configuracao(original), p.hash_configuracao(equivalente))

    def test_nome_curto_identifica_caixa_e_semantica(self):
        nomes = [p.nome_configuracao(item) for item in self.plano["configuracoes"]]
        self.assertEqual(len(set(nomes)), 48)
        for item, nome in zip(self.plano["configuracoes"], nomes):
            self.assertLess(len(nome), 80)
            self.assertTrue(nome.isascii())
            self.assertIn(item["caixa"]["modo"], nome)
            self.assertIn(p.hash_configuracao(item)[:12], nome)

    def test_json_rejeita_duplicadas_constantes_e_utf8_invalido(self):
        for dados in (b'{"versao":1,"versao":1}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":"\xff"}'):
            with self.subTest(dados=dados), self.assertRaises((ValueError, UnicodeError)):
                p.carregar_plano(dados)

    def test_esquema_tipos_orcamento_e_ids_estritos(self):
        for campo, valor in (("versao", True), ("seed", True), ("seed", -1),
                             ("particao", "selecao"), ("etapa", "inspecao"), ("rodada", "round6")):
            with self.subTest(campo=campo, valor=valor):
                plano = deepcopy(self.plano)
                plano[campo] = valor
                self.rejeita(plano)
        for alteracao in ("extra", "remover", "id"):
            plano = deepcopy(self.plano)
            if alteracao == "extra":
                plano["configuracoes"][0]["inativo"] = 0
            elif alteracao == "remover":
                plano["configuracoes"].pop()
            else:
                plano["configuracoes"][1]["id"] = "r1c01"
            self.rejeita(plano)

    def test_quadros_caminhos_hashes_e_composicao_estritos(self):
        for campo, valor in (("quadro", True), ("quadro", 50), ("video_id", "13"),
                             ("imagem", "../fora.jpg"), ("imagem_sha256", "z" * 64)):
            plano = deepcopy(self.plano)
            plano["quadros"][0][campo] = valor
            self.rejeita(plano)
        plano = deepcopy(self.plano)
        plano["quadros"][1] = deepcopy(plano["quadros"][0])
        self.rejeita(plano)

    def test_rejeita_duplicata_semantica_e_alteracao_dos_controles(self):
        plano = deepcopy(self.plano)
        plano["configuracoes"][1]["caixa"] = {"modo": "escala", "fator": 1}
        self.rejeita(plano)
        plano = deepcopy(self.plano)
        plano["configuracoes"][0]["parametros"]["limiar_minimo"] = 20
        self.rejeita(plano)

    def test_rejeita_perfil_e_balanceamento_divergentes(self):
        plano = deepcopy(self.plano)
        plano["configuracoes"][12]["parametros"]["convexidade_minima"] = 0.8
        self.rejeita(plano)
        plano = deepcopy(self.plano)
        for item in plano["configuracoes"][12:18]:
            item["parametros"]["limiar_minimo"] = 10
        self.rejeita(plano)
        plano = deepcopy(self.plano)
        plano["geracao"]["valores_candidatos"]["diametro_maximo_pequeno"] = [6, 8, 10]
        self.rejeita(plano)

    def test_rejeita_fontes_desvinculadas_ou_controles_alterados(self):
        inspecao = json.loads(self.inspecao)
        inspecao["origem_desenvolvimento"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            p.gerar_round1(self.dev, serializar(inspecao))
        inspecao = json.loads(self.inspecao)
        inspecao["configuracoes"][0]["parametros"]["classificacao"]["area_maxima_pequeno"] = 80
        with self.assertRaises(ValueError):
            p.gerar_round1(self.dev, serializar(inspecao))
        inspecao = json.loads(self.inspecao)
        inspecao["quadros"][0]["imagem_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            p.gerar_round1(self.dev, serializar(inspecao))

    def test_orcamentos_das_rodadas_futuras_sem_exigir_desenho_do_round1(self):
        for rodada, quantidade in (("round2", 32), ("round3", 24), ("round4", 18), ("round5", 14)):
            plano = deepcopy(self.plano)
            plano["rodada"] = rodada
            plano["configuracoes"] = plano["configuracoes"][:quantidade]
            plano["geracao"]["quantidade_exploratorias"] = quantidade - 12
            for i, item in enumerate(plano["configuracoes"], 1):
                item["id"] = f"r{rodada[-1]}c{i:02d}"
            self.assertEqual(len(p.carregar_plano(serializar(plano))["configuracoes"]), quantidade)
            plano["configuracoes"].pop()
            self.rejeita(plano)


if __name__ == "__main__":
    unittest.main()
