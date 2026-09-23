"""Integração v5 com entradas temporárias e candidatos sintéticos controlados."""

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from io import StringIO
import math
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import cv2
import numpy as np

from algoritmos.classicos.caixas_blobs import configuracao_caixa_de_dict
from scripts.blobs import executar_rodada as executor
from scripts.blobs.planejamento_round5 import gerar_round5
from scripts.testes import test_executar_rodada_blobs as fixture
from scripts.testes import test_executar_round4_blobs as fixture4


FONTES_PRODUCAO = tuple(executor.FONTES_CODIGO)
FONTE_ROUND5 = "scripts/blobs/planejamento_round5.py"


class ExecutarRound5BlobsTest(unittest.TestCase):
    # Reutiliza a montagem; não herda nem coleta os testes das rodadas anteriores.
    gravar = fixture.RodadaBlobsTest.gravar
    resultado = fixture.RodadaBlobsTest.resultado
    proibir_deteccoes = fixture4.ExecutarRound4BlobsTest.proibir_deteccoes

    def setUp(self):
        fixture4.ExecutarRound4BlobsTest.setUp(self)
        self.round4 = self.plano
        self.caminho_round4 = self.caminho_plano
        self.round4_bytes = self.caminho_round4.read_bytes()
        self.plano = gerar_round5(
            self.round1_bytes, self.round2_bytes, self.round3_bytes, self.round4_bytes,
        )
        self.caminho_plano = self.gravar("scripts/blobs/rodadas/round5.json", fixture.bytes_json(self.plano))
        self.fontes[FONTE_ROUND5] = (fixture.PROJETO / FONTE_ROUND5).read_bytes()
        self.gravar(FONTE_ROUND5, self.fontes[FONTE_ROUND5])
        contexto = patch.object(executor, "FONTES_CODIGO", tuple(self.fontes))
        contexto.start()
        self.addCleanup(contexto.stop)

    def test_preflight_confere_14_por_178_e_363_hashes_sem_detectar_ou_criar_resultados(self):
        with self.proibir_deteccoes():
            dados = executor.congelar_entradas(self.caminho_plano)
            ambiente = executor.conferir_ambiente_e_imagens(dados)
        self.assertEqual(dados["plano"]["versao"], 5)
        self.assertEqual(len(dados["plano"]["configuracoes"]), 14)
        self.assertEqual(len(dados["entradas"]), 178)
        self.assertEqual(len(dados["hashes"]), 363)
        self.assertEqual(len(ambiente["parametros_backend"]), 14)
        self.assertEqual(len(ambiente["parametros_opencv"]), 6)
        self.assertIn("scikit_image_importado", ambiente["dependencias"])
        self.assertEqual(set(dados["origens"]), {
            "origem_desenvolvimento", "origem_inspecao", "origem_round1",
            "origem_round2", "origem_round3", "origem_round4",
        })
        self.assertFalse(self.saida.exists())

    def test_cadeia_completa_preserva_bytes_e_hashes_dos_cinco_planos(self):
        anteriores = (self.round1_bytes, self.round2_bytes, self.round3_bytes, self.round4_bytes)
        caminhos = (
            self.raiz / "scripts/limiarizacao/rodadas/round1.json",
            self.raiz / "scripts/blobs/inspecao/round0.json",
            self.raiz / "scripts/blobs/rodadas/round1.json",
            self.caminho_round2, self.caminho_round3, self.caminho_round4, self.caminho_plano,
        )
        antes = {p: p.read_bytes() for p in caminhos}
        dados = executor.congelar_entradas(self.caminho_plano)
        for numero, conteudo in enumerate(anteriores, 1):
            self.assertEqual(dados["origens"][f"origem_round{numero}"], conteudo)
            self.assertEqual(self.plano[f"origem_round{numero}"]["sha256"], executor.sha256(conteudo))
        for numero, plano in enumerate((self.round2, self.round3, self.round4, self.plano), 1):
            self.assertEqual(plano[f"origem_round{numero}"]["sha256"], executor.sha256(anteriores[numero - 1]))
        for caminho, conteudo in antes.items():
            self.assertEqual(caminho.read_bytes(), conteudo)
            self.assertEqual(dados["hashes"][caminho.relative_to(self.raiz).as_posix()], executor.sha256(conteudo))
        self.assertFalse(self.saida.exists())

    def test_round4_alterado_e_recusado_antes_de_qualquer_saida(self):
        self.caminho_round4.write_bytes(self.round4_bytes + b" ")
        with self.proibir_deteccoes(), self.assertRaisesRegex(ValueError, "Hash divergente.*origem_round4"):
            executor.congelar_entradas(self.caminho_plano)
        self.assertFalse(self.saida.exists())

    def test_elo_interno_rompido_falha_mesmo_com_hash_externo_atualizado(self):
        alterado = deepcopy(self.round4)
        alterado["origem_round3"]["sha256"] = "0" * 64
        conteudo = fixture.bytes_json(alterado)
        self.caminho_round4.write_bytes(conteudo)
        self.plano["origem_round4"]["sha256"] = executor.sha256(conteudo)
        self.caminho_plano.write_bytes(fixture.bytes_json(self.plano))
        with self.proibir_deteccoes(), self.assertRaises(ValueError):
            executor.congelar_entradas(self.caminho_plano)
        self.assertFalse(self.saida.exists())

    def test_cli_conferir_round5_nao_inicia_execucao(self):
        with self.proibir_deteccoes(), \
             patch.object(executor, "executar", side_effect=AssertionError("Não executar.")), \
             redirect_stdout(StringIO()) as saida:
            retorno = executor.main(["--rodada", "round5", "--conferir"])
        self.assertEqual(retorno, 0)
        self.assertIn("14 configurações", saida.getvalue())
        self.assertIn("2492 avaliações", saida.getvalue())
        self.assertFalse(self.saida.exists())

    def test_fonte_round5_consta_do_arquivo_de_reproducao_em_producao(self):
        self.assertIn(FONTE_ROUND5, FONTES_PRODUCAO)

    def test_execucao_mista_exporta_v5_backend_linhagem_hashes_e_chama_relatorio(self):
        with self.proibir_deteccoes():
            dados = executor.congelar_entradas(self.caminho_plano)
            executor.conferir_ambiente_e_imagens(dados)
        # A fixture só é reduzida depois da conferência da grade completa.
        dados["plano"] = deepcopy(dados["plano"])
        dados["plano"]["configuracoes"] = [
            c for c in dados["plano"]["configuracoes"] if c["id"] in ("r5c04", "r5c10", "r5c13")
        ]
        dados["plano"]["quadros"] = dados["plano"]["quadros"][:2]
        dados["entradas"] = dados["entradas"][:2]
        dados["plano_bytes"] = fixture.bytes_json(dados["plano"])
        entradas_antes = deepcopy(dados["entradas"])
        sigmas = {"log": 2 + 2 * (12 - 2) / 9, "dog": 2 * 1.6**2}

        def relatorio_sintetico(pasta):
            # Verifica o contrato da chamada; o conteúdo do PDF tem testes próprios.
            manifesto = executor.carregar_json((pasta / "execucao.json").read_bytes())
            self.assertEqual((manifesto["versao"], manifesto["situacao"]), (5, "concluida"))
            destino = pasta / "relatorios" / "sintetico" / "relatorio.pdf"
            destino.parent.mkdir(parents=True)
            destino.write_bytes(b"%PDF-fixture-sintetica\n")
            return destino

        with patch.object(executor, "congelar_entradas", return_value=dados), \
             patch("algoritmos.classicos.blobs.detectar", return_value=self.resultado()) as sbd, \
             patch("skimage.feature.blob_log", return_value=np.array([[40, 40, sigmas["log"]]])) as log, \
             patch("skimage.feature.blob_dog", return_value=np.array([[40, 40, sigmas["dog"]]])) as dog, \
             patch("analise.relatorio_rodada_blobs.gerar_relatorio", side_effect=relatorio_sintetico) as relatorio, \
             redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            pasta = executor.executar(self.caminho_plano)
        self.assertEqual((sbd.call_count, log.call_count, dog.call_count), (2, 2, 2))
        relatorio.assert_called_once_with(pasta)
        self.assertEqual(dados["entradas"], entradas_antes)
        manifesto = executor.carregar_json((pasta / "execucao.json").read_bytes())
        self.assertEqual((manifesto["versao"], manifesto["rodada"], manifesto["situacao"]), (5, "round5", "concluida"))
        self.assertEqual(manifesto["avaliacoes_concluidas"], 6)
        self.assertEqual(manifesto["configuracoes_concluidas"], 3)
        self.assertEqual(len(manifesto["parametros_backend"]), 3)
        apontador = executor.carregar_json((pasta / "relatorio.json").read_bytes())
        self.assertEqual(apontador["situacao"], "concluido")
        self.assertEqual((self.raiz / apontador["arquivo"]).read_bytes(), b"%PDF-fixture-sintetica\n")
        for nome, conteudo in dados["origens"].items():
            self.assertEqual((pasta / f"{nome}.json").read_bytes(), conteudo)
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
        linhas = fixture.linhas_csv(pasta / "resumo_por_quadro.csv")
        self.assertEqual(len(linhas), 6)
        self.assertEqual(len({(r["configuracao_id"], r["video_id"], r["quadro"]) for r in linhas}), 6)
        for linha in linhas:
            self.assertEqual(int(linha["tempo_preprocessamento_ns"]), 0)
            self.assertEqual(int(linha["tempo_pipeline_ns"]),
                             int(linha["tempo_detector_ns"]) + int(linha["tempo_adaptacao_ns"]))
            self.assertEqual((linha["tp_individuos"], linha["fp_individuos"], linha["fn_individuos"]), ("1", "0", "0"))
        self.assertEqual(len(fixture.linhas_csv(pasta / "resumo_configuracoes.csv")), 3)
        self.assertEqual(len(fixture.linhas_csv(pasta / "ranking.csv")), 3)
        for nome, digest in manifesto["saidas_sha256"].items():
            self.assertEqual(executor.hash_arquivo(self.raiz / nome), digest)

    def test_corte_log_muda_somente_classe_na_faixa_24_a_28_e_preserva_candidatos_e_caixas(self):
        with self.proibir_deteccoes():
            dados = executor.congelar_entradas(self.caminho_plano)
        itens = {c["id"]: c for c in dados["plano"]["configuracoes"]}
        base, variante = itens["r5c13"], itens["r5c14"]
        parametros_esperados = deepcopy(base["parametros"])
        parametros_esperados["classificacao"]["area_minima_aglomerado"] = math.pi * 14**2
        self.assertEqual(variante["parametros"], parametros_esperados)
        self.assertEqual(base["caixa"], variante["caixa"])
        self.assertEqual(base["preprocessamento"], variante["preprocessamento"])
        # Uma escala abaixo da faixa, outra dentro e outra acima: nenhum detector real é chamado.
        candidatos = np.array([[20., 20., 8.666666666666668 - 10 / 9],
                               [40., 40., 9.777777777777779],
                               [60., 60., 10.88888888888889]])
        candidatos_antes = candidatos.copy()
        entrada = dados["entradas"][0]
        entrada_antes = deepcopy(entrada)
        tabelas, predicoes = [], []
        with patch("skimage.feature.blob_log", return_value=candidatos) as backend:
            for item in (base, variante):
                config, detectar = executor.preparar_detector(item)
                destino = self.raiz / "contraste_sintetico" / item["id"]
                executor.executar_quadro(entrada, config, configuracao_caixa_de_dict(item["caixa"]),
                                          item, destino, cv2, np, detectar)
                tabelas.append(fixture.linhas_csv(destino / "deteccoes.csv"))
                predicoes.append([linha.split() for linha in (destino / "predicoes.txt").read_text().splitlines()])
        self.assertEqual(backend.call_count, 2)
        np.testing.assert_array_equal(backend.call_args_list[0].args[0], backend.call_args_list[1].args[0])
        self.assertEqual(backend.call_args_list[0].kwargs, backend.call_args_list[1].kwargs)
        np.testing.assert_array_equal(candidatos, candidatos_antes)
        self.assertEqual(entrada, entrada_antes)
        self.assertEqual([r["classe"] for r in tabelas[0]], ["0", "1", "1"])
        self.assertEqual([r["classe"] for r in tabelas[1]], ["0", "0", "1"])
        for original, alterado in zip(tabelas[0], tabelas[1]):
            self.assertEqual({k: v for k, v in original.items() if k != "classe"},
                             {k: v for k, v in alterado.items() if k != "classe"})
        for original, alterado in zip(predicoes[0], predicoes[1]):
            self.assertEqual(original[1:], alterado[1:])
        central = tabelas[1][1]
        self.assertGreaterEqual(float(central["diametro_blob_px"]), 24)
        self.assertLess(float(central["diametro_blob_px"]), 28)
        self.assertAlmostEqual(float(central["sigma_blob_px"]), 9.777777777777779)
        self.assertAlmostEqual(float(central["area_estimada_blob_px2"]), 2 * math.pi * 9.777777777777779**2)


if __name__ == "__main__":
    unittest.main()
