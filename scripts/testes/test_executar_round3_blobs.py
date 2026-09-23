"""Integração do round3 exclusivamente em arquivos e imagens sintéticos."""

from contextlib import ExitStack, redirect_stderr, redirect_stdout
from copy import deepcopy
from io import StringIO
import math
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import numpy as np

from scripts.blobs import executar_rodada as executor
from scripts.blobs.planejamento_round2 import gerar_round2
from scripts.blobs.planejamento_round3 import gerar_round3
from scripts.testes import test_executar_rodada_blobs as fixture


FONTES_PRODUCAO = tuple(executor.FONTES_CODIGO)
FONTE_ROUND3 = "scripts/blobs/planejamento_round3.py"


class ExecutarRound3BlobsTest(unittest.TestCase):
    # Reutiliza a montagem dos arquivos sem herdar e coletar novamente os testes antigos.
    gravar = fixture.RodadaBlobsTest.gravar
    resultado = fixture.RodadaBlobsTest.resultado

    def setUp(self):
        fixture.RodadaBlobsTest.setUp(self)
        self.round1_bytes = self.caminho_plano.read_bytes()
        self.round2 = gerar_round2(self.round1_bytes)
        self.round2_bytes = fixture.bytes_json(self.round2)
        self.caminho_round2 = self.gravar("scripts/blobs/rodadas/round2.json", self.round2_bytes)
        self.plano = gerar_round3(self.round1_bytes, self.round2_bytes)
        self.caminho_plano = self.gravar("scripts/blobs/rodadas/round3.json", fixture.bytes_json(self.plano))
        self.fontes = {
            "scripts/blobs/executar_rodada.py": b"# fonte sintetica\n",
            FONTE_ROUND3: (fixture.PROJETO / FONTE_ROUND3).read_bytes(),
        }
        for nome, conteudo in self.fontes.items():
            self.gravar(nome, conteudo)
        contexto = patch.object(executor, "FONTES_CODIGO", tuple(self.fontes))
        contexto.start()
        self.addCleanup(contexto.stop)

    def proibir_deteccoes(self):
        contexto = ExitStack()
        for nome in ("algoritmos.classicos.blobs.detectar",
                     "algoritmos.classicos.variantes_blobs.detectar_escala",
                     "algoritmos.classicos.variantes_blobs.aplicar_preprocessamento",
                     "skimage.feature.blob_log", "skimage.feature.blob_dog"):
            contexto.enter_context(patch(nome, side_effect=AssertionError("Preflight não deve detectar.")))
        return contexto

    def test_preflight_confere_24_por_178_e_361_hashes_sem_detectar_ou_criar_resultados(self):
        with self.proibir_deteccoes():
            dados = executor.congelar_entradas(self.caminho_plano)
            ambiente = executor.conferir_ambiente_e_imagens(dados)
        self.assertEqual(dados["plano"]["versao"], 3)
        self.assertEqual(len(dados["plano"]["configuracoes"]), 24)
        self.assertEqual(len(dados["entradas"]), 178)
        self.assertEqual(len(dados["hashes"]), 361)
        self.assertEqual(len(ambiente["parametros_backend"]), 24)
        self.assertEqual(len(ambiente["parametros_opencv"]), 12)
        self.assertIn("scikit_image_importado", ambiente["dependencias"])
        self.assertEqual(set(dados["origens"]), {
            "origem_desenvolvimento", "origem_inspecao", "origem_round1", "origem_round2",
        })
        self.assertFalse(self.saida.exists())

    def test_cadeia_de_origens_permanece_integra_e_preserva_bytes(self):
        antes = {p: p.read_bytes() for p in (
            self.raiz / "scripts/limiarizacao/rodadas/round1.json",
            self.raiz / "scripts/blobs/inspecao/round0.json",
            self.raiz / "scripts/blobs/rodadas/round1.json",
            self.caminho_round2, self.caminho_plano,
        )}
        dados = executor.congelar_entradas(self.caminho_plano)
        self.assertEqual(dados["origens"]["origem_round1"], self.round1_bytes)
        self.assertEqual(dados["origens"]["origem_round2"], self.round2_bytes)
        self.assertEqual(self.round2["origem_round1"]["sha256"], executor.sha256(self.round1_bytes))
        self.assertEqual(self.plano["origem_round2"]["sha256"], executor.sha256(self.round2_bytes))
        for caminho, conteudo in antes.items():
            self.assertEqual(caminho.read_bytes(), conteudo)
            self.assertEqual(dados["hashes"][caminho.relative_to(self.raiz).as_posix()], executor.sha256(conteudo))
        self.assertFalse(self.saida.exists())

    def test_round2_alterado_e_recusado_antes_de_qualquer_saida(self):
        self.caminho_round2.write_bytes(self.round2_bytes + b" ")
        with self.proibir_deteccoes(), self.assertRaisesRegex(ValueError, "Hash divergente.*origem_round2"):
            executor.congelar_entradas(self.caminho_plano)
        self.assertFalse(self.saida.exists())

    def test_cadeia_interna_rompida_e_recusada_mesmo_com_hash_externo_atualizado(self):
        alterado = deepcopy(self.round2)
        alterado["origem_round1"]["sha256"] = "0" * 64
        conteudo = fixture.bytes_json(alterado)
        self.caminho_round2.write_bytes(conteudo)
        self.plano["origem_round2"]["sha256"] = executor.sha256(conteudo)
        self.caminho_plano.write_bytes(fixture.bytes_json(self.plano))
        with self.proibir_deteccoes(), self.assertRaises(ValueError):
            executor.congelar_entradas(self.caminho_plano)
        self.assertFalse(self.saida.exists())

    def test_cli_conferir_round3_nao_inicia_execucao(self):
        with self.proibir_deteccoes(), \
             patch.object(executor, "executar", side_effect=AssertionError("Não executar.")), \
             redirect_stdout(StringIO()) as saida:
            retorno = executor.main(["--rodada", "round3", "--conferir"])
        self.assertEqual(retorno, 0)
        self.assertIn("24 configurações", saida.getvalue())
        self.assertIn("4272 avaliações", saida.getvalue())
        self.assertFalse(self.saida.exists())

    def test_fonte_do_round3_consta_do_arquivo_de_reproducao_em_producao(self):
        self.assertIn(FONTE_ROUND3, FONTES_PRODUCAO)

    def test_execucao_mista_sintetica_registra_versao_backend_sigma_e_fontes(self):
        # Valida primeiro a grade completa. Só então limita a saída deste teste.
        with self.proibir_deteccoes():
            dados = executor.congelar_entradas(self.caminho_plano)
            executor.conferir_ambiente_e_imagens(dados)
        dados["plano"] = deepcopy(dados["plano"])
        dados["plano"]["configuracoes"] = [
            c for c in dados["plano"]["configuracoes"] if c["id"] in ("r3c02", "r3c13", "r3c19")
        ]
        dados["plano"]["quadros"] = dados["plano"]["quadros"][:2]
        dados["entradas"] = dados["entradas"][:2]
        dados["plano_bytes"] = fixture.bytes_json(dados["plano"])
        sigmas = {"log": 2 + 2 * (12 - 2) / 9, "dog": 2 * 1.6**2}
        entradas_antes = deepcopy(dados["entradas"])
        with patch.object(executor, "congelar_entradas", return_value=dados), \
             patch("algoritmos.classicos.blobs.detectar", return_value=self.resultado()) as sbd, \
             patch("skimage.feature.blob_log", return_value=np.array([[40, 40, sigmas["log"]]])) as log, \
             patch("skimage.feature.blob_dog", return_value=np.array([[40, 40, sigmas["dog"]]])) as dog, \
             patch("analise.relatorio_rodada_blobs.gerar_relatorio", side_effect=RuntimeError("PDF sintético")), \
             redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            pasta = executor.executar(self.caminho_plano)
        self.assertEqual((sbd.call_count, log.call_count, dog.call_count), (2, 2, 2))
        self.assertEqual(dados["entradas"], entradas_antes)
        manifesto = executor.carregar_json((pasta / "execucao.json").read_bytes())
        self.assertEqual(manifesto["versao"], 3)
        self.assertEqual(manifesto["rodada"], "round3")
        self.assertEqual(manifesto["situacao"], "concluida")
        self.assertEqual(manifesto["avaliacoes_concluidas"], 6)
        self.assertEqual(manifesto["configuracoes_concluidas"], 3)
        self.assertEqual(len(manifesto["parametros_backend"]), 3)
        self.assertEqual((pasta / "origem_round1.json").read_bytes(), self.round1_bytes)
        self.assertEqual((pasta / "origem_round2.json").read_bytes(), self.round2_bytes)
        self.assertEqual(executor.hash_arquivo(pasta / "codigo.zip"), manifesto["codigo"]["sha256_zip"])
        with ZipFile(pasta / "codigo.zip") as arquivo:
            self.assertEqual(set(arquivo.namelist()), set(self.fontes))
            for nome, conteudo in self.fontes.items():
                self.assertEqual(arquivo.read(nome), conteudo)
                self.assertEqual(manifesto["codigo"]["sha256_arquivos"][nome], executor.sha256(conteudo))
        for execucao in manifesto["execucoes"]:
            config_dir = self.raiz / execucao["pasta"]
            backend = executor.carregar_json((config_dir / "configuracao_backend.json").read_bytes())
            metodo = backend["metodo"]
            self.assertEqual(backend, manifesto["parametros_backend"][execucao["configuracao_id"]])
            self.assertEqual(len(list(config_dir.rglob("comparacao.png"))), 2)
            self.assertEqual(len(list(config_dir.rglob("preprocessamento.png"))), 0)
            for csv in config_dir.rglob("deteccoes.csv"):
                registro = fixture.linhas_csv(csv)[0]
                self.assertEqual(registro["metodo_detector"], metodo)
                self.assertEqual(registro["preprocessamento"], "nenhum")
                self.assertEqual(registro["classe"], "0")
                self.assertEqual(registro["centro_blob_x_px"], "40.0")
                self.assertEqual(registro["area_pixels"], "")
                self.assertGreater(int(registro["caixa_largura_px"]), int(registro["original_caixa_largura_px"]))
                if metodo == "simpleblob":
                    self.assertEqual(registro["origem_medidas"], "simpleblob_keypoint")
                    self.assertEqual(registro["sigma_blob_px"], "")
                else:
                    self.assertEqual(registro["origem_medidas"], metodo + "_sigma")
                    self.assertAlmostEqual(float(registro["sigma_blob_px"]), sigmas[metodo])
                    self.assertAlmostEqual(float(registro["diametro_blob_px"]), 2 * math.sqrt(2) * sigmas[metodo])
                    self.assertAlmostEqual(float(registro["area_estimada_blob_px2"]), 2 * math.pi * sigmas[metodo]**2)
                    self.assertIsNone(backend["parametros"]["threshold_rel"])
                    self.assertFalse(backend["parametros"]["exclude_border"])
        resumo = fixture.linhas_csv(pasta / "resumo_por_quadro.csv")
        self.assertEqual(len(resumo), 6)
        self.assertEqual(len({(r["configuracao_id"], r["video_id"], r["quadro"]) for r in resumo}), 6)
        for linha in resumo:
            self.assertEqual(int(linha["tempo_preprocessamento_ns"]), 0)
            self.assertEqual(int(linha["tempo_pipeline_ns"]),
                             int(linha["tempo_detector_ns"]) + int(linha["tempo_adaptacao_ns"]))
        self.assertEqual(len(fixture.linhas_csv(pasta / "resumo_configuracoes.csv")), 3)
        self.assertEqual(len(fixture.linhas_csv(pasta / "ranking.csv")), 3)
        for nome, digest in manifesto["saidas_sha256"].items():
            self.assertEqual(executor.hash_arquivo(self.raiz / nome), digest)


if __name__ == "__main__":
    unittest.main()
