"""Integração das variantes em imagens sintéticas, sem experimentos na base."""

from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from algoritmos.classicos.caixas_blobs import configuracao_caixa_de_dict
from scripts.blobs import executar_rodada as executor
from scripts.blobs.planejamento_round2 import gerar_round2
from scripts.testes import test_executar_rodada_blobs as fixtures

bytes_json, linhas_csv = fixtures.bytes_json, fixtures.linhas_csv


class VariantesExecutorTest(unittest.TestCase):
    setUp = fixtures.RodadaBlobsTest.setUp
    gravar = fixtures.RodadaBlobsTest.gravar

    def preparar_round2(self):
        self.round2 = gerar_round2(self.caminho_plano.read_bytes())
        return self.gravar("scripts/blobs/rodadas/round2.json", bytes_json(self.round2))

    def test_preflight_variantes_congela_origens_sem_processar_imagens(self):
        caminho = self.preparar_round2()
        with patch("algoritmos.classicos.blobs.detectar", side_effect=AssertionError("detector")), \
             patch("algoritmos.classicos.variantes_blobs.detectar_escala", side_effect=AssertionError("escala")), \
             patch("algoritmos.classicos.variantes_blobs.aplicar_preprocessamento", side_effect=AssertionError("CLAHE")):
            dados = executor.congelar_entradas(caminho)
            ambiente = executor.conferir_ambiente_e_imagens(dados)
        self.assertEqual(len(dados["entradas"]), 178)
        self.assertEqual(len(dados["hashes"]), 360)
        self.assertEqual(dados["origens"]["origem_round1"], self.caminho_plano.read_bytes())
        self.assertEqual(len(ambiente["parametros_backend"]), 32)
        self.assertEqual(len(ambiente["parametros_opencv"]), 24)
        self.assertIn("scikit_image_importado", ambiente["dependencias"])
        self.assertFalse(self.saida.exists())

    def test_fonte_round1_divergente_impede_qualquer_resultado(self):
        caminho = self.preparar_round2()
        self.caminho_plano.write_bytes(self.caminho_plano.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "Hash divergente"):
            executor.congelar_entradas(caminho)
        self.assertFalse(self.saida.exists())

    def test_loG_dog_exportam_sigma_e_preservam_classe_medidas_caixa(self):
        caminho = self.preparar_round2()
        dados = executor.congelar_entradas(caminho)
        for metodo in ("log", "dog"):
            item = next(c for c in self.round2["configuracoes"] if c["metodo"] == metodo)
            config, detector = executor.preparar_detector(item)
            destino = self.raiz / metodo
            entrada = dados["entradas"][0]
            antes = deepcopy(entrada)
            linha, avaliacao = executor.executar_quadro(
                entrada, config, configuracao_caixa_de_dict(item["caixa"]), item,
                destino, cv2, np, detector)
            registros = linhas_csv(destino / "deteccoes.csv")
            self.assertGreater(len(registros), 0)
            self.assertEqual(entrada, antes)
            self.assertTrue(all(r["origem_medidas"] == f"{metodo}_sigma" for r in registros))
            self.assertTrue(all(float(r["sigma_blob_px"]) > 0 for r in registros))
            self.assertTrue(all(r["area_pixels"] == "" for r in registros))
            self.assertTrue(all(r["metodo_detector"] == metodo for r in registros))
            self.assertEqual(linha["tempo_preprocessamento_ns"], 0)
            self.assertEqual(linha["tempo_pipeline_ns"],
                             linha["tempo_detector_ns"] + linha["tempo_adaptacao_ns"])
            self.assertEqual(len((destino / "predicoes.txt").read_text().splitlines()), len(registros))
            self.assertEqual(json.loads((destino / "avaliacao.json").read_text(encoding="utf8"))["metodo_detector"], metodo)
            self.assertFalse((destino / "preprocessamento.png").exists())

    def test_clahe_salva_entrada_processada_e_mede_tempo_separado(self):
        caminho = self.preparar_round2()
        dados = executor.congelar_entradas(caminho)
        item = next(c for c in self.round2["configuracoes"] if c["preprocessamento"]["metodo"] == "clahe")
        config, detector = executor.preparar_detector(item)
        entrada = dados["entradas"][0]
        recebidas = []

        def capturar(imagem, parametros):
            recebidas.append(imagem.copy())
            return detector(imagem, parametros)

        destino = self.raiz / "clahe"
        linha, _ = executor.executar_quadro(entrada, config,
            configuracao_caixa_de_dict(item["caixa"]), item, destino, cv2, np, capturar)
        processada = cv2.imdecode(np.frombuffer((destino / "preprocessamento.png").read_bytes(), np.uint8), 0)
        np.testing.assert_array_equal(processada, recebidas[0])
        self.assertEqual(processada.dtype, np.uint8)
        self.assertGreater(linha["tempo_preprocessamento_ns"], 0)
        self.assertEqual(linha["tempo_pipeline_ns"], sum(linha[f"tempo_{t}_ns"]
                         for t in ("preprocessamento", "detector", "adaptacao")))

    def test_execucao_mista_preserva_manifestos_backend_e_saidas(self):
        caminho = self.preparar_round2()
        dados = executor.congelar_entradas(caminho)
        escolhidas = [dados["plano"]["configuracoes"][0]]
        for metodo, preproc in (("simpleblob", "clahe"), ("log", "nenhum"), ("dog", "nenhum")):
            escolhidas.append(next(c for c in dados["plano"]["configuracoes"]
                                  if c["metodo"] == metodo and c["preprocessamento"]["metodo"] == preproc))
        dados["plano"]["configuracoes"] = escolhidas
        dados["plano"]["quadros"] = dados["plano"]["quadros"][:1]
        dados["entradas"] = dados["entradas"][:1]
        dados["plano_bytes"] = bytes_json(dados["plano"])
        with patch.object(executor, "congelar_entradas", return_value=dados), \
             patch("analise.relatorio_rodada_blobs.gerar_relatorio", side_effect=RuntimeError("PDF simulado")), \
             redirect_stdout(StringIO()):
            pasta = executor.executar(caminho)
        manifesto = json.loads((pasta / "execucao.json").read_text(encoding="utf8"))
        self.assertEqual(manifesto["versao"], 2)
        self.assertEqual(manifesto["situacao"], "concluida")
        self.assertEqual(manifesto["avaliacoes_concluidas"], 4)
        self.assertEqual((pasta / "origem_round1.json").read_bytes(), self.caminho_plano.read_bytes())
        for item, executada in zip(escolhidas, manifesto["execucoes"]):
            diretorio = self.raiz / executada["pasta"]
            backend = json.loads((diretorio / "configuracao_backend.json").read_text(encoding="utf8"))
            self.assertEqual(backend["metodo"], item["metodo"])
            self.assertEqual((diretorio / "configuracao_opencv.json").exists(), item["metodo"] == "simpleblob")
        for nome, digest in manifesto["saidas_sha256"].items():
            self.assertEqual(executor.hash_arquivo(self.raiz / nome), digest)


if __name__ == "__main__":
    unittest.main()
