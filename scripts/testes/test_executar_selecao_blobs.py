"""Integração da seleção com JPEGs sintéticos e candidatos controlados."""

from contextlib import ExitStack, redirect_stderr, redirect_stdout
from copy import deepcopy
from io import StringIO
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import cv2
import numpy as np

from analise.avaliacao_individuos import CRITERIOS
from algoritmos.classicos.comum import Caixa, ClasseObjeto, Deteccao, MedidasBlob, ResultadoDeteccao
from scripts.blobs import executar_inspecao as inspecao
from scripts.blobs import executar_rodada as rodada
from scripts.blobs import executar_selecao as selecao
from scripts.blobs.planejamento import hash_configuracao
from scripts.testes import test_executar_rodada_blobs as fixture


PROJETO = Path(__file__).resolve().parents[2]
FONTES_SELECAO = (
    "scripts/blobs/executar_selecao.py", "scripts/blobs/planejamento_selecao.py",
    "analise/relatorio_selecao_blobs.py",
)
FONTES_PRODUCAO = tuple(selecao.FONTES_CODIGO)


class ExecutarSelecaoBlobsTest(unittest.TestCase):
    def setUp(self):
        temporario = tempfile.TemporaryDirectory()
        self.addCleanup(temporario.cleanup)
        self.raiz = Path(temporario.name)
        self.saida = self.raiz / "resultados/frame-to-frame/blobs"
        for modulo, campo, valor in (
            (rodada, "RAIZ", self.raiz), (rodada, "SAIDA", self.saida),
            (selecao, "RAIZ", self.raiz), (selecao, "SAIDA", self.saida / "selecao"),
            (inspecao, "RAIZ", self.raiz),
        ):
            contexto = patch.object(modulo, campo, valor)
            contexto.start()
            self.addCleanup(contexto.stop)
        anteriores = json.loads((PROJETO / "scripts/blobs/rodadas/round5.json").read_bytes())
        round2 = json.loads((PROJETO / "scripts/blobs/rodadas/round2.json").read_bytes())
        itens = [
            next(c for c in anteriores["configuracoes"] if c["id"] == "r5c04"),
            next(c for c in round2["configuracoes"] if c["id"] == "r2c17"),
            next(c for c in anteriores["configuracoes"] if c["id"] == "r5c13"),
            next(c for c in anteriores["configuracoes"] if c["id"] == "r5c10"),
        ]
        itens = deepcopy(itens)
        for numero, item in enumerate(itens, 1):
            item["id"] = f"s{numero:03d}"
        imagem = np.zeros((80, 80, 3), dtype=np.uint8)
        cv2.circle(imagem, (40, 40), 10, (255, 255, 255), -1)
        sucesso, jpeg = cv2.imencode(".jpg", imagem)
        self.assertTrue(sucesso)
        self.imagem = jpeg.tobytes()
        entradas, hashes = [], {}
        for indice, anotacao in enumerate((b"0 0.5 0.5 0.25 0.25\n1 0.1 0.1 0.1 0.1\n",
                                             b"2 0.5 0.5 0.25 0.25\n")):
            quadro = {"video_id": "13", "quadro": indice * 100}
            for tipo, pasta, extensao, conteudo in (
                ("imagem", "images", "jpg", self.imagem),
                ("anotacao", "labels", "txt", anotacao),
            ):
                nome = f"bases_de_dados/visem_tracking/dataset/Train/13/{pasta}/13_frame_{indice * 100}.{extensao}"
                quadro[tipo] = nome
                quadro[f"{tipo}_sha256"] = rodada.sha256(conteudo)
                hashes[nome] = rodada.sha256(conteudo)
                self.gravar(nome, conteudo)
            entradas.append({"quadro": quadro, "imagem_bytes": self.imagem,
                             "anotacao_bytes": anotacao, "anotacoes": rodada.ler_anotacoes(anotacao)})
        plano = {"versao": 1, "algoritmo": "blobs", "rodada": "selecao", "seed": 42,
                 "etapa": "selecao_imagens", "particao": "selecao", "criterios": deepcopy(CRITERIOS),
                 "configuracoes": itens, "quadros": [e["quadro"] for e in entradas]}
        self.caminho = self.gravar("scripts/blobs/selecao/plano.json", fixture.bytes_json(plano))
        hashes[self.caminho.relative_to(self.raiz).as_posix()] = rodada.hash_arquivo(self.caminho)
        fontes = ("scripts/blobs/executar_rodada.py", "algoritmos/classicos/variantes_blobs.py", *FONTES_SELECAO)
        self.dados = {"plano": plano, "plano_bytes": self.caminho.read_bytes(), "hashes": hashes,
                      "entradas": entradas,
                      "origens": {f"origem_round{n}": fixture.bytes_json({"rodada": f"round{n}"}) for n in range(1, 6)},
                      "codigo": {nome: b"# fonte sintetica\n" for nome in fontes}}
        for nome, conteudo in self.dados["codigo"].items():
            self.gravar(nome, conteudo)

    def gravar(self, nome, conteudo):
        caminho = self.raiz / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(conteudo)
        return caminho

    def impedir_deteccao(self):
        contexto = ExitStack()
        for nome in ("algoritmos.classicos.blobs.detectar", "algoritmos.classicos.variantes_blobs.detectar_escala",
                     "algoritmos.classicos.variantes_blobs.aplicar_preprocessamento",
                     "skimage.feature.blob_log", "skimage.feature.blob_dog"):
            contexto.enter_context(patch(nome, side_effect=AssertionError("Não deveria detectar.")))
        return contexto

    def simular_planejador(self):
        contexto = ExitStack()
        contexto.enter_context(patch.object(selecao, "carregar_plano", return_value=self.dados["plano"]))
        contexto.enter_context(patch.object(selecao, "conferir_origens", return_value=self.dados["origens"]))
        contexto.enter_context(patch.object(selecao, "caminhos_origens", return_value={
            nome: f"fontes/{nome}.json" for nome in self.dados["origens"]}))
        contexto.enter_context(patch.object(selecao, "FONTES_CODIGO", tuple(self.dados["codigo"])))
        return contexto

    def resultado_sbd(self):
        caixa = Caixa(30, 30, 20, 20)
        medidas = MedidasBlob(40., 40., 20., math.pi * 100, 400, False)
        return ResultadoDeteccao("blobs", 80, 80, (Deteccao(ClasseObjeto.NORMAL, caixa, medidas),), None)

    def executar_sintetico(self, *, falha_pdf=False, alterar_disco=False):
        if alterar_disco:
            for entrada in self.dados["entradas"]:
                self.gravar(entrada["quadro"]["imagem"], b"JPEG alterado depois de congelar")
                self.gravar(entrada["quadro"]["anotacao"], b"anotacao alterada depois de congelar")
        recebidas = []

        def sbd(imagem, config):
            recebidas.append(imagem.copy())
            return self.resultado_sbd()

        def pdf(pasta):
            if falha_pdf:
                raise RuntimeError("PDF sintético indisponível")
            manifesto = rodada.carregar_json((pasta / "execucao.json").read_bytes())
            self.assertEqual(manifesto["situacao"], "concluida")
            caminho = pasta / "relatorios" / "sintetico" / "relatorio.pdf"
            caminho.parent.mkdir(parents=True)
            caminho.write_bytes(b"%PDF-fixture-sintetica\n")
            return caminho

        with patch.object(selecao, "congelar_entradas", return_value=self.dados), \
             patch("algoritmos.classicos.blobs.detectar", side_effect=sbd) as detector_sbd, \
             patch("skimage.feature.blob_log", return_value=np.array([[40., 40., 2.]])) as detector_log, \
             patch("skimage.feature.blob_dog", return_value=np.array([[40., 40., 3.2]])) as detector_dog, \
             patch("analise.relatorio_selecao_blobs.gerar_relatorio", side_effect=pdf) as relatorio, \
             redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            pasta = selecao.executar(self.caminho)
        self.assertEqual((detector_sbd.call_count, detector_log.call_count, detector_dog.call_count), (4, 2, 2))
        relatorio.assert_called_once_with(pasta)
        self.assertEqual([x.ndim for x in recebidas], [3, 3, 2, 2])
        np.testing.assert_array_equal(recebidas[0], recebidas[1])
        np.testing.assert_array_equal(recebidas[2], recebidas[3])
        return pasta

    def test_execucao_mista_preserva_bytes_classes_agrupadas_backend_originais_hashes_e_pdf(self):
        antes = deepcopy(self.dados)
        pasta = self.executar_sintetico(alterar_disco=True)
        self.assertEqual(self.dados, antes)
        self.assertEqual(pasta.parent, self.saida / "selecao")
        self.assertFalse((self.saida / "round1").exists())
        manifesto = rodada.carregar_json((pasta / "execucao.json").read_bytes())
        self.assertEqual((manifesto["tipo"], manifesto["etapa"], manifesto["particao"]),
                         ("selecao_blobs", "selecao_imagens", "selecao"))
        self.assertEqual(manifesto["criterios"], CRITERIOS)
        self.assertEqual(manifesto["avaliacoes_concluidas"], 8)
        self.assertEqual(manifesto["configuracoes_concluidas"], 4)
        self.assertEqual(manifesto["quadros_por_configuracao"], 2)
        self.assertFalse(manifesto["aleatoriedade_utilizada"])
        self.assertNotIn("finalistas", manifesto)
        self.assertEqual((pasta / "plano.json").read_bytes(), antes["plano_bytes"])
        for nome, conteudo in antes["origens"].items():
            self.assertEqual((pasta / f"{nome}.json").read_bytes(), conteudo)
        with ZipFile(pasta / "codigo.zip") as arquivo:
            self.assertEqual(set(arquivo.namelist()), set(antes["codigo"]))
            for nome, conteudo in antes["codigo"].items():
                self.assertEqual(arquivo.read(nome), conteudo)
                self.assertEqual(manifesto["codigo"]["sha256_arquivos"][nome], rodada.sha256(conteudo))
        self.assertEqual(manifesto["codigo"]["sha256_zip"], rodada.hash_arquivo(pasta / "codigo.zip"))
        for item, execucao in zip(antes["plano"]["configuracoes"], manifesto["execucoes"]):
            config_dir = self.raiz / execucao["pasta"]
            self.assertEqual(rodada.carregar_json((config_dir / "configuracao.json").read_bytes()), item)
            registro_execucao = rodada.carregar_json((config_dir / "execucao.json").read_bytes())
            self.assertEqual(registro_execucao["tipo"], "selecao_blobs")
            self.assertEqual(registro_execucao["configuracao_sha256"], hash_configuracao(item))
            backend = rodada.carregar_json((config_dir / "configuracao_backend.json").read_bytes())
            self.assertEqual(backend, manifesto["parametros_backend"][item["id"]])
            self.assertEqual(backend["classificacao"], item["parametros"]["classificacao"])
            self.assertEqual(len(list(config_dir.rglob("comparacao.png"))), 2)
            self.assertEqual(len(list(config_dir.rglob("preprocessamento.png"))),
                             2 if item["preprocessamento"]["metodo"] == "clahe" else 0)
            for csv in config_dir.rglob("deteccoes.csv"):
                registro = fixture.linhas_csv(csv)[0]
                self.assertEqual(registro["metodo_detector"], item["metodo"])
                self.assertEqual(registro["preprocessamento"], item["preprocessamento"]["metodo"])
                self.assertEqual(registro["area_pixels"], "")
                self.assertEqual(registro["tempo_segundos"], "")
                self.assertEqual(registro["centro_blob_x_px"], "40.0")
                self.assertGreater(int(registro["caixa_largura_px"]), int(registro["original_caixa_largura_px"]))
                esperado = "2" if item["metodo"] == "log" else "0"
                self.assertEqual(registro["classe"], esperado)
                if item["metodo"] in ("log", "dog"):
                    sigma = 2 if item["metodo"] == "log" else 3.2
                    self.assertAlmostEqual(float(registro["sigma_blob_px"]), sigma)
                    self.assertAlmostEqual(float(registro["diametro_blob_px"]), 2 * math.sqrt(2) * sigma)
                    self.assertAlmostEqual(float(registro["area_estimada_blob_px2"]), 2 * math.pi * sigma**2)
                else:
                    self.assertEqual(registro["sigma_blob_px"], "")
        linhas = fixture.linhas_csv(pasta / "resumo_por_quadro.csv")
        self.assertEqual(len(linhas), 8)
        self.assertEqual(len({(l["configuracao_id"], l["video_id"], l["quadro"]) for l in linhas}), 8)
        for linha in linhas:
            self.assertEqual((linha["tp_individuos"], linha["fp_individuos"], linha["fn_individuos"]), ("1", "0", "0"))
            self.assertEqual(int(linha["tempo_pipeline_ns"]), sum(int(linha[f"tempo_{nome}_ns"])
                             for nome in ("preprocessamento", "detector", "adaptacao")))
            if linha["configuracao_id"] != "s002":
                self.assertEqual(int(linha["tempo_preprocessamento_ns"]), 0)
        totais = fixture.linhas_csv(pasta / "resumo_configuracoes.csv")
        self.assertEqual(len(totais), 4)
        for linha in totais:
            self.assertEqual((linha["tp_individuos"], linha["fp_individuos"], linha["fn_individuos"]), ("2", "0", "0"))
            self.assertEqual((linha["tp_aglomerados"], linha["fp_aglomerados"], linha["fn_aglomerados"]), ("0", "0", "1"))
            self.assertEqual((linha["localizadas_classe_0"], linha["localizadas_classe_2"], linha["pares_incorretos"]), ("1", "1", "1"))
        self.assertEqual(len(fixture.linhas_csv(pasta / "ranking.csv")), 4)
        for nome, digest in manifesto["saidas_sha256"].items():
            self.assertEqual(rodada.hash_arquivo(self.raiz / nome), digest)
        apontador = rodada.carregar_json((pasta / "relatorio.json").read_bytes())
        self.assertEqual(apontador["situacao"], "concluido")
        self.assertTrue((self.raiz / apontador["arquivo"]).is_file())

    def test_falha_pdf_preserva_metricas_e_manifesto_concluidos(self):
        pasta = self.executar_sintetico(falha_pdf=True)
        manifesto = rodada.carregar_json((pasta / "execucao.json").read_bytes())
        self.assertEqual(manifesto["situacao"], "concluida")
        self.assertEqual(manifesto["avaliacoes_concluidas"], 8)
        self.assertEqual(len(fixture.linhas_csv(pasta / "resumo_configuracoes.csv")), 4)
        self.assertEqual(rodada.carregar_json((pasta / "relatorio.json").read_bytes())["situacao"], "falhou")

    def test_erro_de_fonte_ou_hash_interrompe_antes_de_criar_saida(self):
        for erro in (FileNotFoundError("Fonte ausente"), ValueError("Hash divergente")):
            with self.subTest(erro=type(erro).__name__), self.impedir_deteccao(), \
                 patch.object(selecao, "congelar_entradas", side_effect=erro), \
                 self.assertRaises(type(erro)), redirect_stdout(StringIO()):
                selecao.executar(self.caminho)
            self.assertFalse(self.saida.exists())

    def test_congelamento_le_os_mesmos_bytes_de_imagens_anotacoes_fontes_e_planos(self):
        with self.simular_planejador(), self.impedir_deteccao():
            dados = selecao.congelar_entradas(self.caminho)
        self.assertEqual(dados["entradas"], self.dados["entradas"])
        self.assertEqual(dados["origens"], self.dados["origens"])
        self.assertEqual(dados["codigo"], self.dados["codigo"])
        self.assertEqual(dados["plano_bytes"], self.dados["plano_bytes"])
        for entrada in dados["entradas"]:
            for tipo in ("imagem", "anotacao"):
                self.assertEqual(dados["hashes"][entrada["quadro"][tipo]],
                                 rodada.sha256(entrada[f"{tipo}_bytes"]))
        self.assertFalse(self.saida.exists())

    def test_jpeg_alterado_ou_anotacao_ausente_sao_recusados_no_congelamento(self):
        entrada = self.dados["entradas"][0]
        imagem = self.raiz / entrada["quadro"]["imagem"]
        imagem.write_bytes(b"mudou")
        with self.simular_planejador(), self.impedir_deteccao(), self.assertRaisesRegex(ValueError, "Hash divergente"):
            selecao.congelar_entradas(self.caminho)
        imagem.write_bytes(entrada["imagem_bytes"])
        (self.raiz / entrada["quadro"]["anotacao"]).unlink()
        with self.simular_planejador(), self.impedir_deteccao(), self.assertRaises(FileNotFoundError):
            selecao.congelar_entradas(self.caminho)
        self.assertFalse(self.saida.exists())

    def test_fontes_novas_e_dependencias_compartilhadas_sao_arquivadas(self):
        for nome in (*FONTES_SELECAO, "algoritmos/classicos/variantes_blobs.py",
                     "algoritmos/classicos/caixas_blobs.py", "analise/avaliacao_individuos.py",
                     "analise/relatorio_inspecao_blobs.py", "analise/relatorio_rodada_blobs.py",
                     "scripts/limiarizacao/inspecionar_imagem.py", "scripts/blobs/arquivos.py"):
            self.assertIn(nome, FONTES_PRODUCAO)

    def test_preflight_rejeita_jpeg_invalido_antes_de_criar_saida(self):
        self.dados["entradas"][1]["imagem_bytes"] = b"JPEG invalido"
        with self.impedir_deteccao(), patch.object(selecao, "congelar_entradas", return_value=self.dados), \
             self.assertRaisesRegex(ValueError, "Imagem inválida"), redirect_stdout(StringIO()):
            selecao.executar(self.caminho)
        self.assertFalse(self.saida.exists())

    def test_cli_conferir_nao_detecta_nem_inicia_execucao(self):
        with self.impedir_deteccao(), patch.object(selecao, "congelar_entradas", return_value=self.dados), \
             patch.object(selecao, "executar", side_effect=AssertionError("Não executar.")), \
             redirect_stdout(StringIO()) as saida:
            retorno = selecao.main(["--plano", str(self.caminho), "--conferir"])
        self.assertEqual(retorno, 0)
        self.assertIn("4 configurações", saida.getvalue())
        self.assertIn("8 avaliações", saida.getvalue())
        self.assertFalse(self.saida.exists())


class RankingExatoBlobsTest(unittest.TestCase):
    @staticmethod
    def linha(identificador, tp, fp, fn, **extras):
        denominador = 2 * tp + fp + fn
        return {"configuracao_id": identificador, "tp_individuos": tp, "fp_individuos": fp,
                "fn_individuos": fn, "f1_individuos": 2 * tp / denominador if denominador else None, **extras}

    def test_fracoes_distintas_com_mesmo_float_nao_se_tornam_empate(self):
        pior = self.linha("a", 2**60, 2, 0)
        melhor = self.linha("z", 2**60, 1, 0)
        self.assertEqual(pior["f1_individuos"], melhor["f1_individuos"])
        resultado = rodada.ordenar_por_f1([pior, melhor])
        self.assertEqual([r["configuracao_id"] for r in resultado], ["z", "a"])
        self.assertEqual([r["posicao"] for r in resultado], [1, 2])

    def test_empate_racional_preserva_id_visual_sem_desempate_por_classe_ou_tempo(self):
        linhas = [self.linha("z", 1, 2, 0, recall_classe_0=1.0, tempo_pipeline_total_ns=1),
                  self.linha("a", 2, 4, 0, recall_classe_0=0.1, tempo_pipeline_total_ns=999),
                  self.linha("vazio", 0, 0, 0), self.linha("zero", 0, 1, 0)]
        antes = deepcopy(linhas)
        resultado = rodada.ordenar_por_f1(linhas)
        self.assertEqual([r["configuracao_id"] for r in resultado], ["a", "z", "zero", "vazio"])
        self.assertEqual([r["posicao"] for r in resultado], [1, 1, 3, None])
        self.assertEqual(linhas, antes)


if __name__ == "__main__":
    unittest.main()
